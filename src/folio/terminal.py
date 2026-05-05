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
            action=suggest_position_action(position, position_weight(metrics, position)),
            reason=suggest_position_reason(position, position_weight(metrics, position)),
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


def suggest_position_action(position: Position, weight: float) -> str:
    if is_leverage_position(position) and weight >= 0.15:
        return ACTION_TRIM
    if weight >= 0.15:
        return ACTION_TRIM
    if position.pnl_pct <= -20:
        return ACTION_EXIT
    if position.pnl_pct <= -10:
        return ACTION_WATCH
    return ACTION_HOLD


def suggest_position_reason(position: Position, weight: float) -> str:
    if is_leverage_position(position) and weight >= 0.15:
        return "leveraged position above 15% weight"
    if weight >= 0.15:
        return "position above 15% weight"
    if position.pnl_pct <= -20:
        return "loss exceeds -20%; thesis check required"
    if position.pnl_pct <= -10:
        return "loss is material; monitor invalidation trigger"
    return "no deterministic trim/exit trigger in snapshot"


def position_weight(metrics: Metrics, position: Position) -> float:
    return metrics.position_weights.get(position.code, 0.0)


def is_leverage_position(position: Position) -> bool:
    return "레버리지" in position.name


def text_bar(ratio: float, width: int = 24) -> str:
    filled = max(0, min(width, round(ratio * width)))
    return "#" * filled + "-" * (width - filled)


def read_latest_report_text(reports_dir: Path = Path("reports")) -> str:
    candidates = sorted(reports_dir.glob("*/portfolio_analysis_report.md"), reverse=True)
    if not candidates:
        return "No report found. Generate one with `folio report --agentic`."
    return candidates[0].read_text(encoding="utf-8")


def read_latest_workflow_trace(reports_dir: Path = Path("reports")) -> str:
    candidates = sorted(reports_dir.glob("*/portfolio_workflow_trace.md"), reverse=True)
    if not candidates:
        return "No workflow trace found. Generate one with `folio report --agentic`."
    return candidates[0].read_text(encoding="utf-8")
