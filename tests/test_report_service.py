from datetime import date
from pathlib import Path
from stat import S_IMODE

from folio.agentic import LiquidityNeed
from folio.analyzer import calculate_metrics
from folio.config import KISSettings, OpenRouterSettings, Settings
from folio.mock_data import mock_balance
from folio.models import Snapshot
from folio.report_service import (
    ReportRequest,
    generate_report,
    insert_position_action_table,
    report_has_position_action_table,
)


def test_generate_report_no_llm_writes_base_outputs(tmp_path: Path) -> None:
    balance = mock_balance("main")
    snapshot = Snapshot(
        id=1,
        account_id="main",
        ts=balance.ts,
        balance=balance,
        metrics=calculate_metrics(balance),
    )
    settings = Settings(
        env="test",
        db_path=tmp_path / "folio.db",
        kis=KISSettings(
            base_url="https://openapi.koreainvestment.com:9443",
            app_key="",
            app_secret="",
            cano="12345678",
            product_code="01",
            hts_id="",
            token_cache_path=tmp_path / "token.json",
        ),
        openrouter=OpenRouterSettings(
            api_key="",
            base_url="https://openrouter.ai/api/v1",
            site_url="http://localhost",
            app_name="folio",
            advisor_model="advisor",
            advisor_deep_model="deep",
            fast_model="fast",
            dev_model="dev",
            test_model="test",
            extract_model="extract",
        ),
    )

    result = generate_report(
        settings,
        tmp_path,
        ReportRequest(
            account_id="main",
            snapshot=snapshot,
            period="2026-05",
            report_date=date(2026, 5, 5),
            investor_id="tester",
            output_dir=tmp_path / "reports",
            liquidity_need=LiquidityNeed(),
            no_llm=True,
        ),
    )

    assert result.no_llm
    assert result.paths.snapshot_path.exists()
    assert result.paths.briefs_path.exists()
    assert result.paths.visual_path.exists()
    assert not result.paths.report_path.exists()
    assert S_IMODE(result.paths.snapshot_path.stat().st_mode) == 0o600
    assert S_IMODE(result.paths.snapshot_path.parent.stat().st_mode) == 0o700


def test_report_position_action_table_detection() -> None:
    report = """
## Position Action Table

| 티커 | 종목명 | Action | Size | Trigger | Rationale | Confidence |
|---|---|---|---|---|---|---|
| 005930 | 삼성전자 | Hold | 유지 | 조건 | 이유 | medium |
"""

    assert report_has_position_action_table(report)
    assert not report_has_position_action_table("## Action Items\n\n| # | Action |")


def test_insert_position_action_table_after_decision_summary() -> None:
    report = """# Report

## Decision Summary

summary

## Health Score

score
"""
    section = """## Position Action Table

| 티커 | 종목명 | Action | Size | Trigger | Rationale | Confidence |
|---|---|---|---|---|---|---|
| 005930 | 삼성전자 | Hold | 유지 | 조건 | 이유 | medium |"""

    updated = insert_position_action_table(report, section)

    assert updated.index("## Decision Summary") < updated.index("## Position Action Table")
    assert updated.index("## Position Action Table") < updated.index("## Health Score")
