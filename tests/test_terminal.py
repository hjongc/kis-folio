from folio.analyzer import calculate_metrics
from folio.mock_data import mock_balance
from folio.models import Balance, Position, now_utc
from folio.terminal import (
    ACTION_TRIM,
    ACTION_WATCH,
    build_terminal_dashboard,
    clip_text,
    extract_agent_metadata,
    extract_decision_text,
    extract_position_action_table,
    read_latest_agent_runs_text,
    read_latest_report_text,
    read_latest_workflow_trace,
    render_agent_runs_for_tui,
    render_decision_text,
    render_file_manifest_text,
    render_workflow_trace_for_tui,
    split_agent_sections,
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
    llm_table = "| 티커 | Action |\n|---|---|\n| 005930 | Hold |"
    text = render_decision_text(dashboard, llm_decision_text=llm_table)

    assert "LLM Decision Board" in text
    assert "portfolio_analysis_report.md" in text
    assert "005930" in text
    assert "Deterministic" not in text


def test_render_decision_text_without_report_prompts_agentic_run() -> None:
    balance = mock_balance("main")
    dashboard = build_terminal_dashboard(balance, calculate_metrics(balance))
    text = render_decision_text(dashboard)

    assert "No LLM decision report found" in text
    assert "folio report --agentic" in text


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


def test_extract_decision_text_falls_back_to_decision_summary() -> None:
    markdown = """
## Decision Summary

| 항목 | 판단 |
|---|---|
| Overall Stance | Hold |

## Next Section
"""

    text = extract_decision_text(markdown)

    assert "Decision Summary" in text
    assert "Position Action Table was not found" in text
    assert "Overall Stance" in text
    assert "Next Section" not in text


def test_clip_text_truncates_long_text() -> None:
    text = clip_text("x" * 20, max_chars=10)

    assert text.startswith("xxxxxxxxxx")
    assert "truncated" in text


def test_latest_report_readers_return_empty_state(tmp_path) -> None:
    assert "No report found" in read_latest_report_text(tmp_path)
    assert "No workflow trace found" in read_latest_workflow_trace(tmp_path)
    assert "No agent run output found" in read_latest_agent_runs_text(tmp_path)


def test_render_agent_runs_for_tui_splits_agent_blocks() -> None:
    markdown = """
# Multi-Agent Runs

## Allocation Analyst

- model: `fast`
- debate_round: `0`

action_label: Hold
risk_level: medium
allocation output

## Risk Manager

- model: `advisor`
- debate_round: `1`

action_label: Trim
risk_level: high
risk output
"""

    text = render_agent_runs_for_tui(markdown)

    assert "Allocation Analyst" in text
    assert "Risk Manager" in text
    assert "round: `1`" in text
    assert "action: `Trim`" in text
    assert "risk: `high`" in text
    assert "action_label: Trim" in text


def test_split_agent_sections_returns_role_sections() -> None:
    sections = split_agent_sections("# Title\n\n## A\nbody\n## B\nbody")

    assert len(sections) == 2
    assert sections[0][0] == "## A"


def test_extract_agent_metadata_reads_role_decision_lines() -> None:
    section = [
        "## Risk Manager",
        "- model: `advisor`",
        "- debate_round: `2`",
        "- token_usage: `hidden`",
        "action_label: Watch",
        "risk_level: high",
    ]

    metadata = extract_agent_metadata(section)

    assert metadata["model"] == "advisor"
    assert metadata["debate_round"] == "2"
    assert metadata["action_label"] == "Watch"
    assert metadata["risk_level"] == "high"


def test_render_workflow_trace_for_tui_hides_internal_budget_lines() -> None:
    markdown = """
# Portfolio Workflow Trace

## Summary

- engine: `langgraph`
- max_planned_llm_calls: 17
- total_tokens_reported: 100
- total_cost_reported: 0.10
- completed_debate_rounds: 1

## Events

| node | detail |
|---|---|
| Portfolio Manager | final report generated with 300 tokens |
"""

    text = render_workflow_trace_for_tui(markdown)

    assert "max_planned_llm_calls" not in text
    assert "total_tokens_reported" not in text
    assert "total_cost_reported" not in text
    assert "completed_debate_rounds" in text
    assert "final report generated" in text
