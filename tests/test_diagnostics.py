from pathlib import Path

from folio.config import KISSettings, OpenRouterSettings, Settings
from folio.diagnostics import has_errors, redact, validate_settings


def test_validate_settings_rejects_placeholders(tmp_path: Path) -> None:
    settings = Settings(
        env="prod",
        db_path=tmp_path / "folio.db",
        kis=KISSettings(
            base_url="https://openapi.koreainvestment.com:9443",
            app_key="your_kis_app_key",
            app_secret="your_kis_app_secret",
            cano="12345678",
            product_code="01",
            hts_id="hts",
            token_cache_path=tmp_path / "token.json",
        ),
        openrouter=OpenRouterSettings(
            api_key="sk-or-your-key",
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

    issues = validate_settings(settings, tmp_path)

    assert has_errors(issues)
    assert "app-key" not in "\n".join(issue.message for issue in issues)


def test_redact_hides_middle() -> None:
    assert redact("abcdefghij") == "abcd...ghij"
    assert redact("") == "<missing>"

