from datetime import date

from folio.agentic import (
    LiquidityNeed,
    build_agent_briefs,
    choose_agent_model,
    render_agent_briefs_markdown,
    render_agent_runs_markdown,
)
from folio.analyzer import calculate_metrics
from folio.config import OpenRouterSettings
from folio.mock_data import mock_balance
from folio.models import AgentRun, Snapshot, now_utc
from folio.reporting import render_report_prompt, render_snapshot_markdown
from folio.visuals import render_portfolio_svg


def test_render_snapshot_markdown_contains_fact_sections() -> None:
    balance = mock_balance("main")
    snapshot = Snapshot(
        id=1,
        account_id="main",
        ts=balance.ts,
        balance=balance,
        metrics=calculate_metrics(balance),
    )

    markdown = render_snapshot_markdown(snapshot, "2026-05", date(2026, 5, 5))

    assert "type: portfolio-snapshot" in markdown
    assert "## 3. 보유 포지션 (Holdings)" in markdown
    assert "| 005930 | 삼성전자 | 주식 | KR | 전기전자 |" in markdown
    assert "| (CASH) | 예수금 | 현금 | KR | 현금 |" in markdown
    assert "transactions_complete: false" in markdown


def test_render_report_prompt_includes_lenses_template_and_agents() -> None:
    prompt = render_report_prompt(
        "SNAPSHOT", "2026-05", date(2026, 5, 5), "AGENT_BRIEFS"
    )

    assert "Risk Manager" in prompt
    assert "portfolio-analysis-report" in prompt
    assert "SNAPSHOT" in prompt
    assert "AGENT_BRIEFS" in prompt


def test_render_agent_briefs_contains_portfolio_roles() -> None:
    balance = mock_balance("main")
    snapshot = Snapshot(
        id=1,
        account_id="main",
        ts=balance.ts,
        balance=balance,
        metrics=calculate_metrics(balance),
    )

    markdown = render_agent_briefs_markdown(
        build_agent_briefs(snapshot, LiquidityNeed(amount=100000, withdraw_by=date(2026, 5, 25)))
    )

    assert "TradingAgents" in markdown
    assert "Allocation Analyst" in markdown
    assert "Liquidity Planner" in markdown
    assert "Data Gap Analyst" in markdown


def test_render_agent_runs_markdown_contains_roles() -> None:
    markdown = render_agent_runs_markdown(
        [
            AgentRun(
                id=1,
                account_id="main",
                snapshot_id=1,
                ts=now_utc(),
                role="Risk Manager",
                model="test/model",
                input_json={},
                output_markdown="risk output",
                token_usage={},
            )
        ]
    )

    assert "multi-agent-runs" in markdown
    assert "Risk Manager" in markdown
    assert "risk output" in markdown


def test_choose_agent_model_routes_fast_and_deep() -> None:
    settings = OpenRouterSettings(
        api_key="key",
        base_url="https://openrouter.ai/api/v1",
        site_url="http://localhost",
        app_name="folio",
        advisor_model="advisor",
        advisor_deep_model="deep",
        fast_model="fast",
        dev_model="dev",
        test_model="test",
        extract_model="extract",
    )

    assert choose_agent_model(settings, "fast") == "fast"
    assert choose_agent_model(settings, "advisor") == "advisor"
    assert choose_agent_model(settings, "fast", deep=True) == "deep"


def test_render_portfolio_svg_contains_svg() -> None:
    balance = mock_balance("main")
    snapshot = Snapshot(
        id=1,
        account_id="main",
        ts=balance.ts,
        balance=balance,
        metrics=calculate_metrics(balance),
    )

    svg = render_portfolio_svg(snapshot)

    assert svg.startswith("<svg")
    assert "Asset Allocation" in svg
