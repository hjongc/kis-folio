from __future__ import annotations

from datetime import UTC, datetime

from .models import Balance, Position


def mock_balance(account_id: str = "main") -> Balance:
    positions = [
        Position("005930", "삼성전자", 10, 72000, 79000, 790000, 70000, 9.72, "전기전자"),
        Position("000660", "SK하이닉스", 3, 180000, 205000, 615000, 75000, 13.89, "전기전자"),
        Position("035420", "NAVER", 2, 210000, 195000, 390000, -30000, -7.14, "서비스업"),
    ]
    return Balance(
        account_id=account_id,
        ts=datetime.now(tz=UTC),
        cash=250000,
        eval_total=sum(position.eval_amount for position in positions),
        pnl_total=sum(position.pnl for position in positions),
        positions=positions,
    )
