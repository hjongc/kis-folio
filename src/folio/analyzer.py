from __future__ import annotations

from collections import defaultdict

from .models import Balance, Metrics


def calculate_metrics(balance: Balance, top_n: int = 3) -> Metrics:
    total = balance.eval_total
    if total <= 0:
        return Metrics(hhi=0.0, sector_dist={}, top_n_pct=0.0, position_weights={})

    position_weights = {
        position.code: round(position.eval_amount / total, 6)
        for position in balance.positions
        if position.eval_amount > 0
    }
    hhi = sum(weight * weight for weight in position_weights.values())

    sector_totals: dict[str, float] = defaultdict(float)
    for position in balance.positions:
        if position.eval_amount > 0:
            sector_totals[position.sector or "Unknown"] += position.eval_amount
    sector_dist = {
        sector: round(amount / total, 6)
        for sector, amount in sorted(sector_totals.items(), key=lambda item: item[0])
    }

    top_n_pct = sum(sorted(position_weights.values(), reverse=True)[:top_n])
    return Metrics(
        hhi=round(hhi, 6),
        sector_dist=sector_dist,
        top_n_pct=round(top_n_pct, 6),
        position_weights=position_weights,
    )


def portfolio_summary(balance: Balance, metrics: Metrics) -> dict[str, object]:
    return {
        "account_id": balance.account_id,
        "cash": balance.cash,
        "eval_total": balance.eval_total,
        "asset_total": balance.asset_total,
        "pnl_total": balance.pnl_total,
        "hhi": metrics.hhi,
        "sector_dist": metrics.sector_dist,
        "top_n_pct": metrics.top_n_pct,
        "positions": [
            {
                "code": position.code,
                "name": position.name,
                "qty": position.qty,
                "avg_price": position.avg_price,
                "current_price": position.current_price,
                "eval_amount": position.eval_amount,
                "pnl": position.pnl,
                "pnl_pct": position.pnl_pct,
                "sector": position.sector,
                "weight": metrics.position_weights.get(position.code, 0.0),
            }
            for position in balance.positions
        ],
    }

