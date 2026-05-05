from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Settings

PLACEHOLDER_PREFIXES = ("your_", "sk-or-your")


@dataclass(frozen=True)
class DiagnosticIssue:
    level: str
    message: str


def redact(value: str, visible: int = 4) -> str:
    if not value:
        return "<missing>"
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}...{value[-visible:]}"


def looks_placeholder(value: str) -> bool:
    return value == "" or value.startswith(PLACEHOLDER_PREFIXES)


def validate_settings(settings: Settings, repo_root: Path) -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []
    if "openapivts" in settings.kis.base_url:
        issues.append(DiagnosticIssue("error", "KIS_BASE_URL points to paper-trading domain"))
    if not settings.kis.base_url.startswith("https://openapi.koreainvestment.com"):
        issues.append(
            DiagnosticIssue("warning", "KIS_BASE_URL is not the expected production domain")
        )
    if looks_placeholder(settings.kis.app_key):
        issues.append(
            DiagnosticIssue("error", "KIS_APP_KEY_MAIN is missing or still a placeholder")
        )
    if looks_placeholder(settings.kis.app_secret):
        issues.append(
            DiagnosticIssue("error", "KIS_APP_SECRET_MAIN is missing or still a placeholder")
        )
    if len(settings.kis.cano) != 8 or not settings.kis.cano.isdigit():
        issues.append(DiagnosticIssue("error", "KIS_CANO_MAIN must be the 8 digit account prefix"))
    if len(settings.kis.product_code) != 2 or not settings.kis.product_code.isdigit():
        issues.append(
            DiagnosticIssue("error", "KIS_ACNT_PRDT_CD_MAIN must be the 2 digit product code")
        )
    if looks_placeholder(settings.openrouter.api_key):
        issues.append(
            DiagnosticIssue("error", "OPENROUTER_API_KEY is missing or still a placeholder")
        )
    if not settings.openrouter.base_url.startswith("https://openrouter.ai/api/v1"):
        issues.append(
            DiagnosticIssue("warning", "OPENROUTER_BASE_URL is not the expected OpenRouter URL")
        )
    if not (repo_root / "prompts" / "advisor.md").exists() and not (
        repo_root / "src" / "folio" / "prompts" / "advisor.md"
    ).exists():
        issues.append(DiagnosticIssue("error", "advisor prompt file is missing"))
    return issues


def has_errors(issues: list[DiagnosticIssue]) -> bool:
    return any(issue.level == "error" for issue in issues)
