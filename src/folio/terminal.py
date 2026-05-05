from __future__ import annotations

import re
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
    llm_decision_text: str = "",
) -> str:
    del dashboard
    lines = [
        "[b]LLM Decision Board[/b]",
        "Source: latest `portfolio_analysis_report.md`",
        "",
    ]
    if llm_decision_text:
        lines.extend(
            [
                llm_decision_text,
                "",
                "Run `a` to regenerate the agentic report after account changes.",
            ]
        )
        return "\n".join(lines)
    lines.extend(
        [
            "No LLM decision report found.",
            "",
            "Press `a` in the TUI or run `folio report --agentic` to generate:",
            "- Position Action Table",
            "- trigger/action/size rationale",
            "- multi-agent debate output",
            "- Portfolio Manager synthesis",
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
        ("portfolio_workflow_trace.md", "engine and agent event trace"),
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


def read_latest_agent_runs_text(reports_dir: Path = Path("reports")) -> str:
    candidates = sorted(reports_dir.glob("*/portfolio_multi_agent_runs.md"), reverse=True)
    if not candidates:
        return "No agent run output found. Generate one with `folio report --agentic`."
    return render_agent_runs_for_tui(candidates[0].read_text(encoding="utf-8"))


def render_agent_runs_for_tui(markdown: str, max_chars_per_agent: int = 1800) -> str:
    sections = split_agent_sections(markdown)
    if not sections:
        return clip_text(markdown, max_chars=20000)
    lines = [
        "[b]Agent Outputs[/b]",
        "Each block is one agent run. Use the final Report tab for the PM synthesis.",
        "",
    ]
    for section in sections:
        title = section[0].lstrip("# ").strip()
        metadata = extract_agent_metadata(section)
        body = strip_agent_metadata(section[1:])
        lines.extend(
            [
                f"[b]{title}[/b]",
                format_agent_metadata(metadata),
                "-" * 72,
                clip_text(body, max_chars=max_chars_per_agent),
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def extract_agent_metadata(section: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    body = "\n".join(section)
    for key in ["model", "debate_round", "source_agent_runs", "action_label", "risk_level"]:
        for line in body.splitlines():
            stripped = line.strip().strip("-").strip()
            if stripped.lower().startswith(f"{key}:"):
                metadata[key] = stripped.split(":", 1)[1].strip().strip("`")
                break
    return metadata


def format_agent_metadata(metadata: dict[str, str]) -> str:
    fields = [
        ("model", metadata.get("model", "-")),
        ("round", metadata.get("debate_round", "-")),
        ("action", metadata.get("action_label", "-")),
        ("risk", metadata.get("risk_level", "-")),
    ]
    if "source_agent_runs" in metadata:
        fields.append(("sources", metadata["source_agent_runs"]))
    return " | ".join(f"{label}: `{value}`" for label, value in fields)


def strip_agent_metadata(lines: list[str]) -> str:
    cleaned = []
    for line in lines:
        stripped = line.strip()
        is_metadata = stripped.startswith("- model:") or stripped.startswith("- debate_round:")
        is_metadata = is_metadata or stripped.startswith("- source_agent_runs:")
        is_metadata = is_metadata or stripped.startswith("- token_usage:")
        if is_metadata:
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def split_agent_sections(markdown: str) -> list[list[str]]:
    lines = markdown.splitlines()
    require_metadata = "# Multi-Agent Runs" in markdown
    sections: list[list[str]] = []
    current: list[str] = []
    for index, line in enumerate(lines):
        starts_agent_section = line.startswith("## ")
        if starts_agent_section and require_metadata:
            lookahead = "\n".join(lines[index + 1 : index + 7])
            starts_agent_section = "- model:" in lookahead
        if starts_agent_section:
            if current:
                sections.append(current)
            current = [line]
            continue
        if current:
            current.append(line)
    if current:
        sections.append(current)
    return sections


def read_latest_decision_table(reports_dir: Path = Path("reports")) -> str:
    candidates = sorted(reports_dir.glob("*/portfolio_analysis_report.md"), reverse=True)
    if not candidates:
        return ""
    return extract_decision_text(candidates[0].read_text(encoding="utf-8"))


def extract_decision_text(markdown: str) -> str:
    position_table = extract_position_action_table(markdown)
    if position_table:
        return "\n".join(["[b]Position Action Table[/b]", position_table])
    decision_summary = extract_markdown_section(markdown, "## Decision Summary")
    if decision_summary:
        return "\n".join(
            [
                "[b]Decision Summary[/b]",
                "Position Action Table was not found. Regenerate the report to repair it.",
                "",
                clip_text(decision_summary, max_chars=5000),
            ]
        )
    return (
        "Latest report found, but it has no Position Action Table or Decision Summary. "
        "Regenerate with `folio report --agentic`."
    )


def extract_position_action_table(markdown: str, max_rows: int = 8) -> str:
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower().startswith("## position action table"):
            table = collect_markdown_table(lines[index + 1 :], max_rows=max_rows)
            return "\n".join(table)
    return ""


def extract_markdown_section(markdown: str, heading: str) -> str:
    lines = markdown.splitlines()
    start_index: int | None = None
    target = heading.strip().lower()
    for index, line in enumerate(lines):
        if line.strip().lower() == target:
            start_index = index
            break
    if start_index is None:
        return ""
    section: list[str] = []
    for line in lines[start_index:]:
        if section and line.startswith("## "):
            break
        section.append(line)
    return "\n".join(section).strip()


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
    return render_workflow_trace_for_tui(candidates[0].read_text(encoding="utf-8"))


def render_workflow_trace_for_tui(markdown: str) -> str:
    hidden_prefixes = (
        "- max_planned_llm_calls:",
        "- total_tokens_reported:",
        "- total_cost_reported:",
    )
    lines = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith(hidden_prefixes):
            continue
        line = re.sub(
            r"final report generated with [^|]*tokens",
            "final report generated",
            line,
        )
        lines.append(line)
    return clip_text("\n".join(lines), max_chars=12000)
