from datetime import date
from pathlib import Path

from folio.agentic import (
    LiquidityNeed,
    build_agent_briefs,
    choose_agent_model,
    render_agent_briefs_markdown,
    render_agent_runs_markdown,
    render_workflow_trace_markdown,
    run_llm_agent_workflow,
)
from folio.analyzer import calculate_metrics
from folio.config import OpenRouterSettings
from folio.mock_data import mock_balance
from folio.models import AgentRun, Snapshot, WorkflowEvent, now_utc
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


def test_render_workflow_trace_markdown_contains_engine_and_events() -> None:
    run = AgentRun(
        id=1,
        account_id="main",
        snapshot_id=1,
        ts=now_utc(),
        role="Risk Manager",
        model="test/model",
        input_json={},
        output_markdown="risk output",
        token_usage={"total_tokens": 10, "cost": 0.01},
    )
    event = WorkflowEvent(
        ts=now_utc(),
        node="Risk Manager",
        status="ok",
        detail="model=test/model",
        duration_sec=1.25,
    )

    markdown = render_workflow_trace_markdown("local", [event], [run], {"total_tokens": 5})

    assert "portfolio-workflow-trace" in markdown
    assert "engine: local" in markdown
    assert "Risk Manager" in markdown
    assert "total_tokens_reported: 15" in markdown


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


def test_run_local_agent_workflow_with_fake_advisor(monkeypatch) -> None:
    class FakeAdvisor:
        def __init__(self, settings, repo_root: Path) -> None:
            self.settings = settings
            self.repo_root = repo_root

        def generate_markdown(self, system_prompt, user_prompt, model, operation, timeout):
            del system_prompt, user_prompt, timeout
            return (
                f"{operation} using {model}. "
                "This is a sufficiently detailed fake portfolio analysis output.",
                {"total_tokens": 3, "cost": 0.001},
            )

    monkeypatch.setattr("folio.agentic.OpenRouterAdvisor", FakeAdvisor)
    balance = mock_balance("main")
    snapshot = Snapshot(
        id=1,
        account_id="main",
        ts=balance.ts,
        balance=balance,
        metrics=calculate_metrics(balance),
    )
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

    result = run_llm_agent_workflow(
        settings=settings,
        repo_root=Path("."),
        account_id="main",
        snapshot=snapshot,
        snapshot_markdown="SNAPSHOT",
        deterministic_briefs_markdown="BRIEFS",
        liquidity_need=LiquidityNeed(amount=100000, withdraw_by=date(2026, 5, 25)),
        report_prompt="REPORT",
        engine="local",
        debate_rounds=1,
        max_retries=1,
        max_workers=2,
    )

    assert result.engine == "local"
    assert len(result.agent_runs) == 10
    assert "Portfolio Manager Synthesis" in result.trace_markdown
    assert result.final_report.startswith("agent:Portfolio Manager Synthesis")


def test_run_langgraph_agent_workflow_with_fake_advisor(monkeypatch) -> None:
    class FakeAdvisor:
        def __init__(self, settings, repo_root: Path) -> None:
            self.settings = settings
            self.repo_root = repo_root

        def generate_markdown(self, system_prompt, user_prompt, model, operation, timeout):
            del system_prompt, user_prompt, timeout
            return (
                f"{operation} using {model}. "
                "This fake output is long enough to pass validation.",
                {"total_tokens": 2},
            )

    monkeypatch.setattr("folio.agentic.OpenRouterAdvisor", FakeAdvisor)
    balance = mock_balance("main")
    snapshot = Snapshot(
        id=1,
        account_id="main",
        ts=balance.ts,
        balance=balance,
        metrics=calculate_metrics(balance),
    )
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

    result = run_llm_agent_workflow(
        settings=settings,
        repo_root=Path("."),
        account_id="main",
        snapshot=snapshot,
        snapshot_markdown="SNAPSHOT",
        deterministic_briefs_markdown="BRIEFS",
        liquidity_need=LiquidityNeed(),
        report_prompt="REPORT",
        engine="langgraph",
        debate_rounds=1,
        max_retries=0,
    )

    assert result.engine == "langgraph"
    assert len(result.agent_runs) == 10
    assert result.agent_runs[0].role == "Allocation Analyst"
    assert "engine: langgraph" in result.trace_markdown


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
