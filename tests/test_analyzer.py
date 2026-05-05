from folio.analyzer import calculate_metrics, portfolio_summary
from folio.mock_data import mock_balance


def test_calculate_metrics_from_mock_balance() -> None:
    balance = mock_balance("main")
    metrics = calculate_metrics(balance)

    assert metrics.hhi > 0
    assert abs(sum(metrics.position_weights.values()) - 1.0) < 0.00001
    assert metrics.sector_dist["전기전자"] > metrics.sector_dist["서비스업"]
    assert abs(metrics.top_n_pct - 1.0) < 0.00001


def test_portfolio_summary_includes_weights() -> None:
    balance = mock_balance("main")
    metrics = calculate_metrics(balance)
    summary = portfolio_summary(balance, metrics)

    assert summary["account_id"] == "main"
    assert len(summary["positions"]) == 3
    assert summary["positions"][0]["weight"] > 0
