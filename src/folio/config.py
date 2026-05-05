from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _get(name: str, env_file: dict[str, str], default: str = "") -> str:
    return os.environ.get(name) or env_file.get(name) or default


def expand_user_path(value: str) -> Path:
    return Path(value).expanduser()


@dataclass(frozen=True)
class KISSettings:
    base_url: str
    app_key: str
    app_secret: str
    cano: str
    product_code: str
    hts_id: str
    token_cache_path: Path


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    base_url: str
    site_url: str
    app_name: str
    advisor_model: str
    advisor_deep_model: str
    fast_model: str
    dev_model: str
    test_model: str
    extract_model: str
    provider: str = "openrouter"
    max_output_tokens: int = 1600
    max_report_tokens: int = 5000
    max_context_chars: int = 24000
    max_agent_output_chars: int = 5000
    max_llm_calls: int = 12
    max_cost_usd: float | None = None


OpenRouterSettings = LLMSettings


@dataclass(frozen=True)
class Settings:
    env: str
    db_path: Path
    kis: KISSettings
    openrouter: LLMSettings

    @property
    def use_dev_model(self) -> bool:
        return self.env.lower() in {"dev", "test", "local"}

    @property
    def llm(self) -> LLMSettings:
        return self.openrouter


def load_settings(env_path: Path | None = None) -> Settings:
    env_file = _read_env_file(env_path or Path(".env"))
    db_path = expand_user_path(_get("FOLIO_DB_PATH", env_file, "~/.folio/folio.db"))
    token_path = expand_user_path(
        _get("FOLIO_TOKEN_CACHE_PATH", env_file, "~/.folio/kis_token.json")
    )
    return Settings(
        env=_get("FOLIO_ENV", env_file, "prod"),
        db_path=db_path,
        kis=KISSettings(
            base_url=_get("KIS_BASE_URL", env_file, "https://openapi.koreainvestment.com:9443"),
            app_key=_get("KIS_APP_KEY_MAIN", env_file),
            app_secret=_get("KIS_APP_SECRET_MAIN", env_file),
            cano=_get("KIS_CANO_MAIN", env_file),
            product_code=_get("KIS_ACNT_PRDT_CD_MAIN", env_file, "01"),
            hts_id=_get("KIS_HTS_ID", env_file),
            token_cache_path=token_path,
        ),
        openrouter=LLMSettings(
            provider=_get(
                "LLM_PROVIDER", env_file, _get("OPENROUTER_PROVIDER", env_file, "openrouter")
            ),
            api_key=_get("LLM_API_KEY", env_file, _get("OPENROUTER_API_KEY", env_file)),
            base_url=_get(
                "LLM_BASE_URL",
                env_file,
                _get("OPENROUTER_BASE_URL", env_file, "https://openrouter.ai/api/v1"),
            ),
            site_url=_get(
                "LLM_SITE_URL", env_file, _get("OPENROUTER_SITE_URL", env_file, "http://localhost")
            ),
            app_name=_get(
                "LLM_APP_NAME", env_file, _get("OPENROUTER_APP_NAME", env_file, "kis-folio")
            ),
            advisor_model=_get(
                "LLM_MODEL_ADVISOR",
                env_file,
                _get("OPENROUTER_MODEL_ADVISOR", env_file, "anthropic/claude-sonnet-4.6"),
            ),
            advisor_deep_model=_get(
                "LLM_MODEL_ADVISOR_DEEP",
                env_file,
                _get("OPENROUTER_MODEL_ADVISOR_DEEP", env_file, "anthropic/claude-opus-4.7"),
            ),
            fast_model=_get(
                "LLM_MODEL_FAST",
                env_file,
                _get("OPENROUTER_MODEL_FAST", env_file, "anthropic/claude-haiku-4.5"),
            ),
            dev_model=_get(
                "LLM_MODEL_DEV",
                env_file,
                _get("OPENROUTER_MODEL_DEV", env_file, "google/gemini-3-flash-preview"),
            ),
            test_model=_get(
                "LLM_MODEL_TEST",
                env_file,
                _get("OPENROUTER_MODEL_TEST", env_file, "deepseek/deepseek-v3.2"),
            ),
            extract_model=_get(
                "LLM_MODEL_EXTRACT",
                env_file,
                _get("OPENROUTER_MODEL_EXTRACT", env_file, "openai/gpt-5.4-nano"),
            ),
            max_output_tokens=int(_get("LLM_MAX_OUTPUT_TOKENS", env_file, "1600")),
            max_report_tokens=int(_get("LLM_MAX_REPORT_TOKENS", env_file, "5000")),
            max_context_chars=int(_get("LLM_MAX_CONTEXT_CHARS", env_file, "24000")),
            max_agent_output_chars=int(_get("LLM_MAX_AGENT_OUTPUT_CHARS", env_file, "5000")),
            max_llm_calls=int(_get("LLM_MAX_CALLS", env_file, "12")),
            max_cost_usd=parse_optional_float(
                _get("LLM_MAX_COST_USD", env_file, _get("OPENROUTER_MAX_COST_USD", env_file))
            ),
        ),
    )


def parse_optional_float(value: str) -> float | None:
    if not value:
        return None
    return float(value)
