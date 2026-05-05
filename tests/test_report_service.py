from datetime import date
from pathlib import Path

from folio.agentic import LiquidityNeed
from folio.analyzer import calculate_metrics
from folio.config import KISSettings, OpenRouterSettings, Settings
from folio.mock_data import mock_balance
from folio.models import Snapshot
from folio.report_service import ReportRequest, generate_report


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
