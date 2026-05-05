from folio.analyzer import calculate_metrics
from folio.mock_data import mock_balance
from folio.terminal import ACTION_TRIM, build_terminal_dashboard, text_bar


def test_build_terminal_dashboard_includes_actions_and_bars() -> None:
    balance = mock_balance("main")
    dashboard = build_terminal_dashboard(balance, calculate_metrics(balance))

    assert dashboard.asset_total > 0
    assert dashboard.overall_action in {"Increase", "Hold", "Trim", "Exit", "Watch"}
    assert dashboard.positions
    assert dashboard.positions[0].action in {"Increase", "Hold", "Trim", "Exit", "Watch"}
    assert len(dashboard.allocation_bars) == 4


def test_terminal_dashboard_trims_large_positions() -> None:
    balance = mock_balance("main")
    dashboard = build_terminal_dashboard(balance, calculate_metrics(balance))

    assert dashboard.positions[0].action == ACTION_TRIM


def test_text_bar_has_stable_width() -> None:
    assert len(text_bar(0.5, width=10)) == 10
    assert text_bar(2.0, width=10) == "##########"
    assert text_bar(-1.0, width=10) == "----------"
