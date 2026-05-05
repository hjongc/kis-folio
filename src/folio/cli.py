from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from .advisor import AdvisorError, OpenRouterAdvisor, local_advisor_output
from .agentic import (
    LiquidityNeed,
    build_agent_briefs,
    render_agent_briefs_markdown,
    render_agent_runs_markdown,
    run_llm_agent_workflow,
)
from .analyzer import calculate_metrics
from .config import load_settings
from .db import (
    active_account,
    init_db,
    latest_snapshot,
    list_accounts,
    list_advisor_outputs,
    save_advisor_output,
    save_agent_run,
    save_snapshot,
    set_active_account,
    upsert_account,
)
from .diagnostics import DiagnosticIssue, has_errors, redact, validate_settings
from .kis import KISClient, KISError
from .mock_data import mock_balance
from .models import Account, AdvisorOutput, Balance, Snapshot
from .reporting import default_report_paths, render_report_prompt, render_snapshot_markdown
from .tui import run_dashboard
from .visuals import render_portfolio_svg


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = load_settings(Path(args.env_file) if args.env_file else None)
    repo_root = Path(__file__).resolve().parents[2]

    try:
        if args.command is None:
            return cmd_tui(args, settings, repo_root)
        return args.func(args, settings, repo_root)
    except (AdvisorError, KISError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="folio")
    parser.add_argument("--env-file", default=".env")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init-db")
    init.set_defaults(func=cmd_init_db)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--network", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    status = sub.add_parser("status")
    status.add_argument("--mock", action="store_true")
    status.set_defaults(func=cmd_status)

    analyze = sub.add_parser("analyze")
    analyze.add_argument("--mock", action="store_true")
    analyze.add_argument("--deep", action="store_true")
    analyze.set_defaults(func=cmd_analyze)

    history = sub.add_parser("history")
    history.add_argument("--limit", type=int, default=10)
    history.set_defaults(func=cmd_history)

    report = sub.add_parser("report")
    report.add_argument("--mock", action="store_true")
    report.add_argument("--deep", action="store_true")
    report.add_argument("--agentic", action="store_true")
    report.add_argument("--agent-engine", choices=["langgraph", "local"], default="langgraph")
    report.add_argument("--debate-rounds", type=int, default=1)
    report.add_argument("--agent-retries", type=int, default=2)
    report.add_argument("--agent-workers", type=int, default=4)
    report.add_argument("--no-llm", action="store_true")
    report.add_argument("--period")
    report.add_argument("--report-date")
    report.add_argument("--investor-id", default="hjongc")
    report.add_argument("--output-dir", default="reports")
    report.add_argument("--cash-need", type=float)
    report.add_argument("--needed-by")
    report.add_argument("--withdraw-by")
    report.set_defaults(func=cmd_report)

    account = sub.add_parser("account")
    account_sub = account.add_subparsers(dest="account_command", required=True)
    account_add = account_sub.add_parser("add")
    account_add.add_argument("--id", required=True)
    account_add.add_argument("--label", required=True)
    account_add.add_argument("--cano", required=True)
    account_add.add_argument("--product-code", default="01")
    account_add.add_argument("--appkey-ref", default="MAIN")
    account_add.set_defaults(func=cmd_account_add)
    account_list = account_sub.add_parser("list")
    account_list.set_defaults(func=cmd_account_list)
    account_use = account_sub.add_parser("use")
    account_use.add_argument("id")
    account_use.set_defaults(func=cmd_account_use)
    return parser


def cmd_init_db(args: argparse.Namespace, settings, repo_root: Path) -> int:
    del args, repo_root
    init_db(settings.db_path)
    print(f"initialized {settings.db_path}")
    return 0


def cmd_doctor(args: argparse.Namespace, settings, repo_root: Path) -> int:
    issues = validate_settings(settings, repo_root)
    try:
        accounts = list_accounts(settings.db_path)
    except OSError as exc:
        issues.append(DiagnosticIssue("error", f"cannot open DB path: {exc}"))
        accounts = []
    if not accounts:
        issues.append(DiagnosticIssue("warning", "no account is registered in SQLite yet"))

    print("folio production diagnostics")
    print(f"env={settings.env}")
    print(f"db_path={settings.db_path}")
    print(f"token_cache_path={settings.kis.token_cache_path}")
    print(f"kis_base_url={settings.kis.base_url}")
    print(f"kis_app_key={redact(settings.kis.app_key)}")
    print(f"openrouter_model={settings.openrouter.advisor_model}")
    print(f"openrouter_api_key={redact(settings.openrouter.api_key)}")
    for account in accounts:
        marker = "*" if account.is_active else " "
        print(
            f"account {marker} {account.id} {account.label} "
            f"{account.account_no}-{account.product_code}"
        )
    for issue in issues:
        print(f"{issue.level}: {issue.message}")

    if has_errors(issues):
        return 1

    if args.network:
        token = KISClient(settings.kis).get_token()
        print(f"kis_token=ok expires_at={token.expires_at.isoformat()}")
    return 0


def cmd_account_add(args: argparse.Namespace, settings, repo_root: Path) -> int:
    del repo_root
    account = Account(
        id=args.id,
        label=args.label,
        account_no=args.cano,
        product_code=args.product_code,
        kis_appkey_ref=args.appkey_ref,
    )
    upsert_account(settings.db_path, account)
    print(f"saved account {account.id}")
    return 0


def cmd_account_list(args: argparse.Namespace, settings, repo_root: Path) -> int:
    del args, repo_root
    for account in list_accounts(settings.db_path):
        marker = "*" if account.is_active else " "
        print(
            f"{marker} {account.id}\t{account.label}\t"
            f"{account.account_no}-{account.product_code}"
        )
    return 0


def cmd_account_use(args: argparse.Namespace, settings, repo_root: Path) -> int:
    del repo_root
    set_active_account(settings.db_path, args.id)
    print(f"active account: {args.id}")
    return 0


def cmd_status(args: argparse.Namespace, settings, repo_root: Path) -> int:
    del repo_root
    account_id = current_account_id(settings)
    snapshot, from_fallback = load_snapshot(args.mock, settings, account_id)
    balance = snapshot.balance
    print_status(balance, snapshot.metrics)
    print(f"snapshot_id={snapshot.id}")
    if from_fallback:
        print(
            "warning: displayed latest saved snapshot because live KIS fetch failed",
            file=sys.stderr,
        )
    return 0


def cmd_analyze(args: argparse.Namespace, settings, repo_root: Path) -> int:
    account_id = current_account_id(settings)
    snapshot, from_fallback = load_snapshot(args.mock, settings, account_id)
    balance = snapshot.balance
    snapshot_id = snapshot.id
    if args.mock:
        output = local_advisor_output(account_id, snapshot_id, balance, snapshot.metrics)
    else:
        output = OpenRouterAdvisor(settings.openrouter, repo_root).analyze(
            account_id=account_id,
            snapshot_id=snapshot_id,
            balance=balance,
            metrics=snapshot.metrics,
            deep=args.deep,
        )
    output_id = save_advisor_output(settings.db_path, output)
    print_advisor_output(output)
    print(f"advisor_output_id={output_id}")
    if from_fallback:
        print(
            "warning: analyzed latest saved snapshot because live KIS fetch failed",
            file=sys.stderr,
        )
    return 0


def cmd_history(args: argparse.Namespace, settings, repo_root: Path) -> int:
    del repo_root
    account_id = current_account_id(settings)
    outputs = list_advisor_outputs(settings.db_path, account_id=account_id, limit=args.limit)
    if outputs:
        print("advisor outputs:")
        for output in outputs:
            print(
                f"- #{output.id} {output.ts.isoformat()} "
                f"snapshot={output.snapshot_id} model={output.model}"
            )
            print(f"  summary: {output.cards.summary}")
        return 0
    snapshot = latest_snapshot(settings.db_path, account_id)
    if snapshot is None:
        print("no snapshots")
        return 0
    print(f"latest snapshot #{snapshot.id} {snapshot.ts.isoformat()}")
    print_status(snapshot.balance, snapshot.metrics)
    return 0


def cmd_report(args: argparse.Namespace, settings, repo_root: Path) -> int:
    account_id = current_account_id(settings)
    snapshot, from_fallback = load_snapshot(args.mock, settings, account_id)
    report_date = parse_report_date(args.report_date)
    period = args.period or report_date.strftime("%Y-%m")
    paths = default_report_paths(Path(args.output_dir), period)
    snapshot_markdown = render_snapshot_markdown(
        snapshot=snapshot,
        period=period,
        report_date=report_date,
        investor_id=args.investor_id,
    )
    liquidity_need = LiquidityNeed(
        amount=args.cash_need,
        needed_by=parse_optional_date(args.needed_by),
        withdraw_by=parse_optional_date(args.withdraw_by),
    )
    agent_briefs = build_agent_briefs(snapshot, liquidity_need=liquidity_need)
    agent_briefs_markdown = render_agent_briefs_markdown(agent_briefs)
    visual_svg = render_portfolio_svg(snapshot)
    write_text(paths.snapshot_path, snapshot_markdown)
    write_text(paths.briefs_path, agent_briefs_markdown)
    write_text(paths.visual_path, visual_svg)
    print(f"snapshot={paths.snapshot_path}")
    print(f"agent_briefs={paths.briefs_path}")
    print(f"visual={paths.visual_path}")

    if args.no_llm:
        if from_fallback:
            print(
                "warning: used latest saved snapshot because live KIS fetch failed",
                file=sys.stderr,
            )
        return 0

    prompt = render_report_prompt(
        snapshot_markdown,
        period=period,
        report_date=report_date,
        agent_briefs_markdown=agent_briefs_markdown,
    )
    if args.agentic:
        workflow = run_llm_agent_workflow(
            settings=settings.openrouter,
            repo_root=repo_root,
            account_id=account_id,
            snapshot=snapshot,
            snapshot_markdown=snapshot_markdown,
            deterministic_briefs_markdown=agent_briefs_markdown,
            liquidity_need=liquidity_need,
            report_prompt=prompt,
            deep=args.deep,
            engine=args.agent_engine,
            debate_rounds=max(args.debate_rounds, 0),
            max_retries=max(args.agent_retries, 0),
            max_workers=max(args.agent_workers, 1),
        )
        saved_runs = []
        for run in workflow.agent_runs:
            run.id = save_agent_run(settings.db_path, run)
            saved_runs.append(run)
        multi_agent_markdown = render_agent_runs_markdown(saved_runs)
        write_text(paths.multi_agent_path, multi_agent_markdown)
        write_text(paths.workflow_trace_path, workflow.trace_markdown)
        print(f"multi_agent_runs={paths.multi_agent_path}")
        print(f"workflow_trace={paths.workflow_trace_path}")
        report_markdown, usage = workflow.final_report, workflow.final_usage
    else:
        advisor = OpenRouterAdvisor(settings.openrouter, repo_root)
        report_markdown, usage = advisor.generate_markdown_report(prompt=prompt, deep=args.deep)
    write_text(paths.report_path, report_markdown)
    print(f"report={paths.report_path}")
    if usage:
        print(f"token_usage={usage}")
    if from_fallback:
        print(
            "warning: reported on latest saved snapshot because live KIS fetch failed",
            file=sys.stderr,
        )
    return 0


def cmd_tui(args: argparse.Namespace, settings, repo_root: Path) -> int:
    del repo_root
    account_id = current_account_id(settings)
    snapshot, _from_fallback = load_snapshot(False, settings, account_id)
    balance = snapshot.balance
    run_dashboard(balance, snapshot.metrics)
    return 0


def current_account_id(settings) -> str:
    account = active_account(settings.db_path)
    return account.id if account else "main"


def load_balance(mock: bool, settings, account_id: str) -> Balance:
    if mock:
        return mock_balance(account_id)
    return KISClient(settings.kis).get_balance(account_id)


def load_snapshot(mock: bool, settings, account_id: str) -> tuple[Snapshot, bool]:
    try:
        balance = load_balance(mock, settings, account_id)
    except KISError:
        if mock:
            raise
        snapshot = latest_snapshot(settings.db_path, account_id)
        if snapshot is None:
            raise
        return snapshot, True
    snapshot = build_snapshot(balance)
    snapshot.id = save_snapshot(settings.db_path, snapshot)
    return snapshot, False


def build_snapshot(balance: Balance) -> Snapshot:
    metrics = calculate_metrics(balance)
    return Snapshot(
        id=None,
        account_id=balance.account_id,
        ts=datetime.now(tz=UTC),
        balance=balance,
        metrics=metrics,
    )


def print_status(balance: Balance, metrics) -> None:
    print(f"account={balance.account_id}")
    print(
        f"eval_total={balance.eval_total:,.0f} "
        f"cash={balance.cash:,.0f} pnl={balance.pnl_total:,.0f}"
    )
    print(f"hhi={metrics.hhi:.3f} top3={metrics.top_n_pct:.1%}")
    print("positions:")
    for position in sorted(balance.positions, key=lambda item: item.eval_amount, reverse=True):
        weight = metrics.position_weights.get(position.code, 0.0)
        print(
            f"- {position.code} {position.name} "
            f"weight={weight:.1%} eval={position.eval_amount:,.0f} "
            f"pnl={position.pnl:,.0f} sector={position.sector}"
        )


def print_advisor_output(output: AdvisorOutput) -> None:
    print(f"model={output.model}")
    print(f"summary: {output.cards.summary}")
    print("risks:")
    for item in output.cards.risks:
        print(f"- {item}")
    print("watchlist:")
    for item in output.cards.watchlist:
        print(f"- {item}")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def parse_report_date(value: str | None):
    if value:
        return datetime.strptime(value, "%Y-%m-%d").date()
    return datetime.now().date()


def parse_optional_date(value: str | None):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


if __name__ == "__main__":
    raise SystemExit(main())
