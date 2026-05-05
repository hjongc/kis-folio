from pathlib import Path

from folio.advisor import local_advisor_output
from folio.analyzer import calculate_metrics
from folio.cli import load_snapshot
from folio.config import KISSettings, OpenRouterSettings, Settings
from folio.db import (
    active_account,
    latest_snapshot,
    list_accounts,
    list_advisor_outputs,
    list_agent_runs,
    save_advisor_output,
    save_agent_run,
    save_snapshot,
    set_active_account,
    upsert_account,
)
from folio.mock_data import mock_balance
from folio.models import Account, AgentRun, Snapshot, now_utc


def test_account_snapshot_and_advisor_persistence(tmp_path: Path) -> None:
    db_path = tmp_path / "folio.db"
    account = Account(id="main", label="Main", account_no="12345678", product_code="01")
    upsert_account(db_path, account)

    assert list_accounts(db_path)[0].id == "main"
    assert active_account(db_path).id == "main"
    set_active_account(db_path, "main")

    balance = mock_balance("main")
    metrics = calculate_metrics(balance)
    snapshot = Snapshot(None, "main", balance.ts, balance, metrics)
    snapshot_id = save_snapshot(db_path, snapshot)

    restored = latest_snapshot(db_path, "main")
    assert restored is not None
    assert restored.id == snapshot_id
    assert restored.metrics.hhi == metrics.hhi

    output = local_advisor_output("main", snapshot_id, balance, metrics)
    output_id = save_advisor_output(db_path, output)
    assert output_id == 1
    outputs = list_advisor_outputs(db_path, account_id="main")
    assert outputs[0].id == output_id
    assert outputs[0].cards.summary == output.cards.summary

    agent_run_id = save_agent_run(
        db_path,
        AgentRun(
            id=None,
            account_id="main",
            snapshot_id=snapshot_id,
            ts=now_utc(),
            role="Risk Manager",
            model="test/model",
            input_json={"task": "risk"},
            output_markdown="risk output",
            token_usage={"total_tokens": 10},
        ),
    )
    agent_runs = list_agent_runs(db_path, account_id="main", snapshot_id=snapshot_id)
    assert agent_runs[0].id == agent_run_id
    assert agent_runs[0].role == "Risk Manager"


def test_load_snapshot_falls_back_to_latest_saved_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "folio.db"
    balance = mock_balance("main")
    metrics = calculate_metrics(balance)
    snapshot_id = save_snapshot(db_path, Snapshot(None, "main", balance.ts, balance, metrics))
    settings = Settings(
        env="prod",
        db_path=db_path,
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
            advisor_model="anthropic/claude-sonnet-4.6",
            advisor_deep_model="anthropic/claude-opus-4.7",
            fast_model="anthropic/claude-haiku-4.5",
            dev_model="google/gemini-3-flash-preview",
            test_model="deepseek/deepseek-v3.2",
            extract_model="openai/gpt-5.4-nano",
        ),
    )

    restored, from_fallback = load_snapshot(False, settings, "main")

    assert from_fallback
    assert restored.id == snapshot_id
