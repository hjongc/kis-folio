from folio.analyzer import calculate_metrics
from folio.mock_data import mock_balance
from folio.models import Balance, Position, now_utc
from folio.terminal import (
    ACTION_TRIM,
    ACTION_WATCH,
    build_terminal_dashboard,
    clip_text,
    extract_position_action_table,
    read_latest_report_text,
    read_latest_workflow_trace,
    render_decision_text,
    render_file_manifest_text,
    text_bar,
)


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


def test_render_decision_text_contains_action_table() -> None:
    balance = mock_balance("main")
    dashboard = build_terminal_dashboard(balance, calculate_metrics(balance))
    text = render_decision_text(dashboard)

    assert "Decision Board" in text
    assert "Action" in text
    assert "Legend" in text
    assert "Trim" in text
    assert "no deterministic trim/exit trigger" not in text
    assert "sector" in text


def test_render_file_manifest_text_lists_outputs() -> None:
    text = render_file_manifest_text("2026-05")

    assert "reports/2026-05/" in text
    assert "portfolio_analysis_report.md" in text


def test_terminal_dashboard_watches_crowded_sector_positions() -> None:
    balance = Balance(
        account_id="main",
        ts=now_utc(),
        cash=100_000,
        eval_total=1_000_000,
        pnl_total=10_000,
        positions=[
            Position("A", "Alpha", 1, 100, 100, 90_000, 1_000, 1.0, "반도체"),
            Position("B", "Beta", 1, 100, 100, 450_000, 1_000, 1.0, "반도체"),
            Position("C", "Core", 1, 100, 100, 460_000, 1_000, 1.0, "금융"),
        ],
    )

    dashboard = build_terminal_dashboard(balance, calculate_metrics(balance))
    row = next(position for position in dashboard.positions if position.code == "A")

    assert row.action == ACTION_WATCH
    assert "crowded sector" in row.reason


def test_extract_position_action_table_reads_latest_report_section() -> None:
    markdown = """
## Position Action Table

| 티커 | 종목명 | Action | Size | Trigger | Rationale | Confidence |
|---|---|---|---|---|---|---|
| 005930 | 삼성전자 | Hold | 유지 | 15% 이하 | core | medium |

## Health Score
"""

    table = extract_position_action_table(markdown)

    assert "005930" in table
    assert "Health Score" not in table


def test_clip_text_truncates_long_text() -> None:
    text = clip_text("x" * 20, max_chars=10)

    assert text.startswith("xxxxxxxxxx")
    assert "truncated" in text


def test_latest_report_readers_return_empty_state(tmp_path) -> None:
    assert "No report found" in read_latest_report_text(tmp_path)
    assert "No workflow trace found" in read_latest_workflow_trace(tmp_path)
