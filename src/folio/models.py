from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class Account:
    id: str
    label: str
    account_no: str
    product_code: str
    kis_appkey_ref: str = "MAIN"
    is_active: bool = True
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class Position:
    code: str
    name: str
    qty: int
    avg_price: float
    current_price: float
    eval_amount: float
    pnl: float
    pnl_pct: float
    sector: str = "Unknown"

    @property
    def weight(self) -> float:
        return 0.0


@dataclass
class PriceBar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class Balance:
    account_id: str
    ts: datetime
    cash: float
    eval_total: float
    pnl_total: float
    positions: list[Position]

    @property
    def asset_total(self) -> float:
        return self.cash + self.eval_total


@dataclass
class Metrics:
    hhi: float
    sector_dist: dict[str, float]
    top_n_pct: float
    position_weights: dict[str, float]


@dataclass
class Snapshot:
    id: int | None
    account_id: str
    ts: datetime
    balance: Balance
    metrics: Metrics
    market_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdvisorCards:
    summary: str
    risks: list[str]
    watchlist: list[str]


@dataclass
class AdvisorOutput:
    id: int | None
    account_id: str
    snapshot_id: int | None
    ts: datetime
    model: str
    prompt_git_ref: str
    tool_calls: list[dict[str, Any]]
    cards: AdvisorCards
    token_usage: dict[str, Any]


@dataclass
class AgentRun:
    id: int | None
    account_id: str
    snapshot_id: int | None
    ts: datetime
    role: str
    model: str
    input_json: dict[str, Any]
    output_markdown: str
    token_usage: dict[str, Any]
