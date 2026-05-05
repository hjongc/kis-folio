from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import Balance, Metrics, Position
from .reporting import infer_asset_class, safe_ratio

ACTION_INCREASE = "Increase"
ACTION_HOLD = "Hold"
ACTION_TRIM = "Trim"
ACTION_EXIT = "Exit"
ACTION_WATCH = "Watch"


@dataclass(frozen=True)
class TerminalPositionRow:
    code: str
    name: str
    weight: float
    eval_amount: float
    pnl: float
    pnl_pct: float
    sector: str
    sector_weight: float
    action: str
    reason: str


@dataclass(frozen=True)
class TerminalDashboard:
    account_id: str
    eval_total: float
    cash: float
    asset_total: float
    pnl_total: float
    hhi: float
    top3: float
    leverage_weight: float
    cash_weight: float
    overall_action: str
    overall_reason: str
    positions: list[TerminalPositionRow]
    allocation_bars: list[tuple[str, float]]


ACTION_TONE = {
    ACTION_INCREASE: "green",
    ACTION_HOLD: "cyan",
    ACTION_TRIM: "yellow",
    ACTION_EXIT: "red",
    ACTION_WATCH: "magenta",
}


def build_terminal_dashboard(balance: Balance, metrics: Metrics) -> TerminalDashboard:
    asset_total = balance.asset_total
    positions = sorted(balance.positions, key=lambda item: item.eval_amount, reverse=True)
    leverage_amount = sum(
        position.eval_amount for position in positions if is_leverage_position(position)
    )
    etf_amount = sum(
        position.eval_amount for position in positions if infer_asset_class(position) == "ETF"
    )
    stock_amount = sum(
        position.eval_amount for position in positions if infer_asset_class(position) == "주식"
    )
    rows = [
        TerminalPositionRow(
            code=position.code,
            name=position.name,
            weight=position_weight(metrics, position),
            eval_amount=position.eval_amount,
            pnl=position.pnl,
            pnl_pct=position.pnl_pct,
            sector=position.sector,
            sector_weight=sector_weight(metrics, position),
            action=suggest_position_action(
                position,
                position_weight(metrics, position),
                sector_weight(metrics, position),
            ),
            reason=suggest_position_reason(
                position,
                position_weight(metrics, position),
                sector_weight(metrics, position),
            ),
        )
        for position in positions
    ]
    leverage_weight = safe_ratio(leverage_amount, asset_total)
    cash_weight = safe_ratio(balance.cash, asset_total)
    overall_action, overall_reason = suggest_overall_action(metrics, leverage_weight, cash_weight)
    return TerminalDashboard(
        account_id=balance.account_id,
        eval_total=balance.eval_total,
        cash=balance.cash,
        asset_total=asset_total,
        pnl_total=balance.pnl_total,
        hhi=metrics.hhi,
        top3=metrics.top_n_pct,
        leverage_weight=leverage_weight,
        cash_weight=cash_weight,
        overall_action=overall_action,
        overall_reason=overall_reason,
        positions=rows,
        allocation_bars=[
            ("ETF", safe_ratio(etf_amount, asset_total)),
            ("Stock", safe_ratio(stock_amount, asset_total)),
            ("Cash", cash_weight),
            ("Leverage", leverage_weight),
        ],
    )


def suggest_overall_action(
    metrics: Metrics, leverage_weight: float, cash_weight: float
) -> tuple[str, str]:
    if leverage_weight >= 0.25 or metrics.top_n_pct >= 0.5:
        return ACTION_TRIM, "concentration or leverage exposure is elevated"
    if cash_weight >= 0.35:
        return ACTION_WATCH, "cash is high; wait for explicit deployment trigger"
    return ACTION_HOLD, "risk concentration is not extreme under current snapshot"


def suggest_position_action(position: Position, weight: float, sector_weight: float) -> str:
    if is_leverage_position(position) and weight >= 0.15:
        return ACTION_TRIM
    if weight >= 0.15:
        return ACTION_TRIM
    if position.pnl_pct <= -20:
        return ACTION_EXIT
    if position.pnl_pct <= -10:
        return ACTION_WATCH
    if position.pnl_pct >= 30:
        return ACTION_WATCH
    if sector_weight >= 0.4 and weight >= 0.05:
        return ACTION_WATCH
    if is_leverage_position(position):
        return ACTION_WATCH
    return ACTION_HOLD


def suggest_position_reason(position: Position, weight: float, sector_weight: float) -> str:
    traits = []
    if is_leverage_position(position):
        traits.append("leveraged ETF")
    else:
        traits.append(infer_asset_class(position).lower())
    traits.append(f"sector {position.sector or 'Unknown'} {sector_weight:.1%}")
    traits.append(pnl_bucket(position.pnl_pct))
    if is_leverage_position(position) and weight >= 0.15:
        return "; ".join([*traits, f"weight {weight:.1%} > 15% cap"])
    if weight >= 0.15:
        return "; ".join([*traits, f"weight {weight:.1%} > 15% cap"])
    if position.pnl_pct <= -20:
        return "; ".join([*traits, "loss beyond -20%; thesis invalidation review"])
    if position.pnl_pct <= -10:
        return "; ".join([*traits, "loss beyond -10%; define recovery/exit trigger"])
    if position.pnl_pct >= 30:
        return "; ".join([*traits, "large gain; define trailing stop or trim trigger"])
    if sector_weight >= 0.4 and weight >= 0.05:
        return "; ".join([*traits, "crowded sector; avoid adding without new trigger"])
    if is_leverage_position(position):
        return "; ".join([*traits, "below size cap; monitor daily volatility"])
    return "; ".join([*traits, f"weight {weight:.1%} below size cap"])


def position_weight(metrics: Metrics, position: Position) -> float:
    return metrics.position_weights.get(position.code, 0.0)


def sector_weight(metrics: Metrics, position: Position) -> float:
    return metrics.sector_dist.get(position.sector or "Unknown", 0.0)


def pnl_bucket(pnl_pct: float) -> str:
    if pnl_pct >= 30:
        return f"large gain {pnl_pct:+.1f}%"
    if pnl_pct >= 15:
        return f"strong gain {pnl_pct:+.1f}%"
    if pnl_pct >= 3:
        return f"modest gain {pnl_pct:+.1f}%"
    if pnl_pct > -3:
        return f"near flat {pnl_pct:+.1f}%"
    if pnl_pct > -10:
        return f"mild drawdown {pnl_pct:+.1f}%"
    return f"material drawdown {pnl_pct:+.1f}%"


def is_leverage_position(position: Position) -> bool:
    return "레버리지" in position.name


def text_bar(ratio: float, width: int = 24) -> str:
    filled = max(0, min(width, round(ratio * width)))
    return "#" * filled + "-" * (width - filled)


def render_decision_text(
    dashboard: TerminalDashboard,
    limit: int = 12,
    llm_decision_text: str = "",
) -> str:
    lines = [
        "[b]Decision Board[/b]",
        f"Portfolio stance: [{ACTION_TONE[dashboard.overall_action]}]"
        f"{dashboard.overall_action}[/] - {dashboard.overall_reason}",
        "",
    ]
    if llm_decision_text:
        lines.extend(
            [
                "[b]Latest LLM Position Actions[/b]",
                llm_decision_text,
                "",
                "[b]Deterministic Snapshot Rules[/b]",
            ]
        )
    lines.extend(
        [
            "Action     Code     Weight    PnL%       Eval KRW        Reason",
            "-" * 78,
        ]
    )
    for row in dashboard.positions[:limit]:
        action = f"[{ACTION_TONE[row.action]}]{row.action:<9}[/]"
        lines.append(
            f"{action} {row.code:<8} {row.weight:>6.1%} "
            f"{row.pnl_pct:>+8.2f}% {row.eval_amount:>14,.0f}  {row.reason}"
        )
    lines.extend(
        [
            "",
            "[b]Legend[/b]",
            "Increase: add only when the report gives a trigger and sizing.",
            "Hold: no deterministic action from the current snapshot.",
            "Trim: reduce concentration, leverage, or oversized exposure.",
            "Exit: thesis damage or loss threshold requires explicit review.",
            "Watch: wait for invalidation or entry trigger before acting.",
        ]
    )
    return "\n".join(lines)


def render_overview_text(dashboard: TerminalDashboard) -> str:
    return "\n".join(
        [
            "[b]Account Snapshot[/b]",
            f"Account     {dashboard.account_id}",
            f"Total       {dashboard.asset_total:,.0f} KRW",
            f"Invested    {dashboard.eval_total:,.0f} KRW",
            f"Cash        {dashboard.cash:,.0f} KRW ({dashboard.cash_weight:.1%})",
            f"PnL         {dashboard.pnl_total:,.0f} KRW",
            "",
            "[b]Risk Gauges[/b]",
            f"HHI         {dashboard.hhi:.3f}",
            f"Top 3       {dashboard.top3:.1%}",
            f"Leverage    {dashboard.leverage_weight:.1%}",
        ]
    )


def render_allocation_text(dashboard: TerminalDashboard) -> str:
    lines = ["[b]Allocation[/b]"]
    for label, ratio in dashboard.allocation_bars:
        lines.append(f"{label:<9} {text_bar(ratio, width=22)} {ratio:>6.1%}")
    return "\n".join(lines)


def render_file_manifest_text(period: str | None = None) -> str:
    base = f"reports/{period}/" if period else "reports/<YYYY-MM>/"
    files = [
        ("portfolio_snapshot.md", "fact-only portfolio input"),
        ("portfolio_agent_briefs.md", "deterministic analyst briefs"),
        ("portfolio_multi_agent_runs.md", "role-by-role LLM outputs"),
        ("portfolio_workflow_trace.md", "engine, events, token and cost trace"),
        ("portfolio_visual.svg", "visual portfolio summary"),
        ("portfolio_analysis_report.md", "final action-oriented report"),
    ]
    lines = [f"[b]Output Folder[/b] {base}", ""]
    lines.extend(f"{name:<34} {description}" for name, description in files)
    return "\n".join(lines)


def clip_text(text: str, max_chars: int = 12000) -> str:
    if len(text) <= max_chars:
        return text
    suffix = "\n\n[truncated in TUI; open the markdown file for full text]"
    return text[:max_chars].rstrip() + suffix


def read_latest_report_text(reports_dir: Path = Path("reports")) -> str:
    candidates = sorted(reports_dir.glob("*/portfolio_analysis_report.md"), reverse=True)
    if not candidates:
        return "No report found. Generate one with `folio report --agentic`."
    return clip_text(candidates[0].read_text(encoding="utf-8"))


def read_latest_decision_table(reports_dir: Path = Path("reports")) -> str:
    candidates = sorted(reports_dir.glob("*/portfolio_analysis_report.md"), reverse=True)
    if not candidates:
        return ""
    return extract_position_action_table(candidates[0].read_text(encoding="utf-8"))


def extract_position_action_table(markdown: str, max_rows: int = 8) -> str:
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower().startswith("## position action table"):
            table = collect_markdown_table(lines[index + 1 :], max_rows=max_rows)
            return "\n".join(table)
    return ""


def collect_markdown_table(lines: list[str], max_rows: int) -> list[str]:
    table: list[str] = []
    data_rows = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if table:
                break
            continue
        if not stripped.startswith("|"):
            if table:
                break
            continue
        is_separator = set(stripped.replace("|", "").strip()) <= {"-", ":", " "}
        if len(table) < 2 or data_rows < max_rows or is_separator:
            table.append(stripped)
        if len(table) >= 2 and not is_separator:
            data_rows += 1
    return table


def read_latest_workflow_trace(reports_dir: Path = Path("reports")) -> str:
    candidates = sorted(reports_dir.glob("*/portfolio_workflow_trace.md"), reverse=True)
    if not candidates:
        return "No workflow trace found. Generate one with `folio report --agentic`."
    return clip_text(candidates[0].read_text(encoding="utf-8"))
