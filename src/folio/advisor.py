from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

from .analyzer import portfolio_summary
from .config import LLMSettings
from .logging_utils import external_call
from .models import AdvisorCards, AdvisorOutput, Balance, Metrics
from .reporting import SYSTEM_PROMPT


class AdvisorError(RuntimeError):
    pass


def prompt_git_ref(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "nogit"
    return result.stdout.strip() or "nogit"


class OpenAICompatibleAdvisor:
    def __init__(self, settings: LLMSettings, repo_root: Path) -> None:
        self.settings = settings
        self.repo_root = repo_root

    def analyze(
        self,
        account_id: str,
        snapshot_id: int | None,
        balance: Balance,
        metrics: Metrics,
        deep: bool = False,
    ) -> AdvisorOutput:
        if not self.settings.api_key:
            raise AdvisorError(f"{self.settings.provider} API key is not configured")
        model = self.settings.advisor_deep_model if deep else self.settings.advisor_model
        prompt = read_advisor_prompt(self.repo_root)
        summary = portfolio_summary(balance, metrics)
        response = self._chat(
            model=model,
            system_prompt=prompt,
            max_tokens=min(self.settings.max_output_tokens, 1000),
            user_payload={
                "instruction": "Review this portfolio summary and return JSON cards.",
                "output_contract": (
                    "Return only one JSON object. Do not include markdown, code fences, "
                    "headings, prose, or commentary outside JSON."
                ),
                "tool_name": "get_portfolio_summary",
                "tool_result": summary,
                "json_schema": {
                    "summary": "string",
                    "risks": ["string"],
                    "watchlist": ["string"],
                },
            },
        )
        cards = parse_cards(response["content"])
        return AdvisorOutput(
            id=None,
            account_id=account_id,
            snapshot_id=snapshot_id,
            ts=datetime.now(tz=UTC),
            model=model,
            prompt_git_ref=prompt_git_ref(self.repo_root),
            tool_calls=[{"name": "get_portfolio_summary", "result": summary}],
            cards=cards,
            token_usage=response.get("usage", {}),
        )

    def _chat(
        self,
        model: str,
        system_prompt: str,
        user_payload: dict[str, Any],
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        req = urllib.request.Request(
            self.settings.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers=self.headers(),
            method="POST",
        )
        with external_call(self.settings.provider, f"chat_completions:{model}"):
            try:
                with urllib.request.urlopen(req, timeout=35) as response:
                    raw = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise AdvisorError(f"{self.settings.provider} HTTP {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                raise AdvisorError(f"{self.settings.provider} network error: {exc.reason}") from exc
        content = raw["choices"][0]["message"]["content"]
        return {"content": content, "usage": raw.get("usage", {})}

    def generate_markdown_report(
        self, prompt: str, deep: bool = False
    ) -> tuple[str, dict[str, Any]]:
        if not self.settings.api_key:
            raise AdvisorError(f"{self.settings.provider} API key is not configured")
        model = self.settings.advisor_deep_model if deep else self.settings.advisor_model
        return self.generate_markdown(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            model=model,
            operation=f"markdown_report:{model}",
            timeout=60,
            max_tokens=self.settings.max_report_tokens,
        )

    def generate_markdown(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        operation: str,
        timeout: float = 60,
        max_tokens: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        if not self.settings.api_key:
            raise AdvisorError(f"{self.settings.provider} API key is not configured")
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        req = urllib.request.Request(
            self.settings.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers=self.headers(),
            method="POST",
        )
        with external_call(self.settings.provider, operation):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    raw = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise AdvisorError(f"{self.settings.provider} HTTP {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                raise AdvisorError(f"{self.settings.provider} network error: {exc.reason}") from exc
        return raw["choices"][0]["message"]["content"], raw.get("usage", {})

    def headers(self) -> dict[str, str]:
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.settings.api_key}",
        }
        if self.settings.provider.lower() == "openrouter":
            headers["http-referer"] = self.settings.site_url
            headers["x-title"] = self.settings.app_name
        return headers


OpenRouterAdvisor = OpenAICompatibleAdvisor


def parse_cards(content: str) -> AdvisorCards:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = extract_json_object(content)
    summary = str(parsed.get("summary", "")).strip()
    risks = [str(item).strip() for item in parsed.get("risks", []) if str(item).strip()][:3]
    watchlist = [str(item).strip() for item in parsed.get("watchlist", []) if str(item).strip()][:3]
    if not summary:
        raise AdvisorError("Advisor response omitted summary")
    return AdvisorCards(summary=summary, risks=risks, watchlist=watchlist)


def extract_json_object(content: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, flags=re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and start < end:
        candidates.append(content[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise AdvisorError("Advisor response was not valid JSON")


def read_advisor_prompt(repo_root: Path) -> str:
    repo_prompt = repo_root / "prompts" / "advisor.md"
    if repo_prompt.exists():
        return repo_prompt.read_text(encoding="utf-8")
    return resources.files("folio.prompts").joinpath("advisor.md").read_text(encoding="utf-8")


def local_advisor_output(
    account_id: str,
    snapshot_id: int | None,
    balance: Balance,
    metrics: Metrics,
    model: str = "local/mock-advisor",
) -> AdvisorOutput:
    summary = portfolio_summary(balance, metrics)
    risks: list[str] = []
    if metrics.top_n_pct >= 0.7:
        risks.append(f"상위 3개 종목 비중이 {metrics.top_n_pct:.1%}로 집중도가 높습니다.")
    if metrics.hhi >= 0.25:
        risks.append(f"HHI가 {metrics.hhi:.3f}로 특정 종목 영향이 큽니다.")
    if not risks:
        risks.append("현재 mock 데이터 기준으로 단일 리스크가 두드러지지는 않습니다.")
    watchlist = [
        "섹터 비중 변화가 손익 변동을 얼마나 설명하는지 관찰할 필요가 있습니다.",
        "현금 비중과 평가손익 변화를 같은 스냅샷 기준으로 비교해 볼 수 있습니다.",
    ]
    return AdvisorOutput(
        id=None,
        account_id=account_id,
        snapshot_id=snapshot_id,
        ts=datetime.now(tz=UTC),
        model=model,
        prompt_git_ref="local",
        tool_calls=[{"name": "get_portfolio_summary", "result": summary}],
        cards=AdvisorCards(
            summary=(
                f"평가금액 {balance.eval_total:,.0f}원, "
                f"총 손익 {balance.pnl_total:,.0f}원입니다."
            ),
            risks=risks[:3],
            watchlist=watchlist[:3],
        ),
        token_usage={},
    )
