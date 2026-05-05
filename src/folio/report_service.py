from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .advisor import OpenAICompatibleAdvisor
from .agentic import (
    LiquidityNeed,
    build_agent_briefs,
    render_agent_briefs_markdown,
    render_agent_runs_markdown,
    run_llm_agent_workflow,
)
from .config import Settings
from .db import save_agent_run
from .models import Snapshot
from .reporting import (
    ReportPaths,
    default_report_paths,
    render_report_prompt,
    render_snapshot_markdown,
)
from .security import ensure_private_directory
from .visuals import render_portfolio_svg


@dataclass(frozen=True)
class ReportRequest:
    account_id: str
    snapshot: Snapshot
    period: str
    report_date: date
    investor_id: str
    output_dir: Path
    liquidity_need: LiquidityNeed
    no_llm: bool = False
    agentic: bool = False
    deep: bool = False
    agent_engine: str = "langgraph"
    debate_rounds: int = 3
    agent_retries: int = 2
    agent_workers: int = 4


@dataclass(frozen=True)
class ReportResult:
    paths: ReportPaths
    usage: dict
    agentic: bool
    no_llm: bool


def generate_report(settings: Settings, repo_root: Path, request: ReportRequest) -> ReportResult:
    paths = default_report_paths(request.output_dir, request.period)
    snapshot_markdown = render_snapshot_markdown(
        snapshot=request.snapshot,
        period=request.period,
        report_date=request.report_date,
        investor_id=request.investor_id,
    )
    agent_briefs = build_agent_briefs(request.snapshot, liquidity_need=request.liquidity_need)
    agent_briefs_markdown = render_agent_briefs_markdown(agent_briefs)
    visual_svg = render_portfolio_svg(request.snapshot)
    write_text(paths.snapshot_path, snapshot_markdown)
    write_text(paths.briefs_path, agent_briefs_markdown)
    write_text(paths.visual_path, visual_svg)

    if request.no_llm:
        return ReportResult(paths=paths, usage={}, agentic=False, no_llm=True)

    prompt = render_report_prompt(
        snapshot_markdown,
        period=request.period,
        report_date=request.report_date,
        agent_briefs_markdown=agent_briefs_markdown,
    )
    if request.agentic:
        workflow = run_llm_agent_workflow(
            settings=settings.llm,
            repo_root=repo_root,
            account_id=request.account_id,
            snapshot=request.snapshot,
            snapshot_markdown=snapshot_markdown,
            deterministic_briefs_markdown=agent_briefs_markdown,
            liquidity_need=request.liquidity_need,
            report_prompt=prompt,
            deep=request.deep,
            engine=request.agent_engine,
            debate_rounds=max(request.debate_rounds, 0),
            max_retries=max(request.agent_retries, 0),
            max_workers=max(request.agent_workers, 1),
        )
        saved_runs = []
        final_report, repair_usage = ensure_position_action_table(
            advisor=OpenAICompatibleAdvisor(settings.llm, repo_root),
            report_markdown=workflow.final_report,
            snapshot_markdown=snapshot_markdown,
            agent_briefs_markdown=agent_briefs_markdown,
            deep=request.deep,
        )
        if final_report != workflow.final_report and workflow.agent_runs:
            workflow.agent_runs[-1].output_markdown = final_report
            workflow.agent_runs[-1].token_usage = merge_usage(
                workflow.agent_runs[-1].token_usage, repair_usage
            )
        for run in workflow.agent_runs:
            run.id = save_agent_run(settings.db_path, run)
            saved_runs.append(run)
        write_text(paths.multi_agent_path, render_agent_runs_markdown(saved_runs))
        write_text(paths.workflow_trace_path, workflow.trace_markdown)
        write_text(paths.report_path, final_report)
        return ReportResult(
            paths=paths,
            usage=merge_usage(workflow.final_usage, repair_usage),
            agentic=True,
            no_llm=False,
        )

    advisor = OpenAICompatibleAdvisor(settings.llm, repo_root)
    report_markdown, usage = advisor.generate_markdown_report(prompt=prompt, deep=request.deep)
    report_markdown, repair_usage = ensure_position_action_table(
        advisor=advisor,
        report_markdown=report_markdown,
        snapshot_markdown=snapshot_markdown,
        agent_briefs_markdown=agent_briefs_markdown,
        deep=request.deep,
    )
    write_text(paths.report_path, report_markdown)
    return ReportResult(
        paths=paths,
        usage=merge_usage(usage, repair_usage),
        agentic=False,
        no_llm=False,
    )


def write_text(path: Path, content: str) -> None:
    ensure_private_directory(path.parent)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def ensure_position_action_table(
    advisor: OpenAICompatibleAdvisor,
    report_markdown: str,
    snapshot_markdown: str,
    agent_briefs_markdown: str,
    deep: bool = False,
) -> tuple[str, dict[str, Any]]:
    if report_has_position_action_table(report_markdown):
        return report_markdown, {}
    model = (
        advisor.settings.advisor_deep_model
        if deep
        else advisor.settings.advisor_model
    )
    section, usage = advisor.generate_markdown(
        system_prompt=(
            "You repair a Korean portfolio report. Return only one markdown section: "
            "## Position Action Table followed by a markdown table with columns "
            "티커, 종목명, Action, Size, Trigger, Rationale, Confidence. "
            "Use only holdings/cash in the snapshot. Do not mention unavailable "
            "personal constraints unless they are present in the snapshot."
        ),
        user_prompt=(
            "portfolio_snapshot.md:\n\n"
            f"{snapshot_markdown}\n\n"
            "portfolio_agent_briefs.md:\n\n"
            f"{agent_briefs_markdown}\n\n"
            "current_report.md:\n\n"
            f"{report_markdown}\n"
        ),
        model=model,
        operation="report:repair_position_action_table",
        timeout=90,
        max_tokens=advisor.settings.max_report_tokens,
    )
    cleaned_section = normalize_position_action_section(section)
    return insert_position_action_table(report_markdown, cleaned_section), usage


def report_has_position_action_table(markdown: str) -> bool:
    lower = markdown.lower()
    if "## position action table" not in lower:
        return False
    after = lower.split("## position action table", 1)[1]
    return "| 티커" in after or "| ticker" in after


def normalize_position_action_section(section: str) -> str:
    stripped = section.strip()
    if stripped.lower().startswith("## position action table"):
        return stripped
    return "## Position Action Table\n\n" + stripped


def insert_position_action_table(report_markdown: str, section: str) -> str:
    lines = report_markdown.splitlines()
    insert_after = find_section_end(lines, "## Decision Summary")
    if insert_after is None:
        insert_after = find_section_end(lines, "## Executive Summary (3줄 요약)")
    if insert_after is None:
        return section.rstrip() + "\n\n" + report_markdown.rstrip() + "\n"
    updated = [*lines[:insert_after], "", section.rstrip(), "", *lines[insert_after:]]
    return "\n".join(updated).rstrip() + "\n"


def find_section_end(lines: list[str], heading: str) -> int | None:
    start: int | None = None
    target = heading.strip().lower()
    for index, line in enumerate(lines):
        if line.strip().lower() == target:
            start = index
            break
    if start is None:
        return None
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            return index
    return len(lines)


def merge_usage(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    if not secondary:
        return primary
    merged = dict(primary)
    for key, value in secondary.items():
        if isinstance(value, int | float) and isinstance(merged.get(key), int | float):
            merged[key] = merged[key] + value
        elif key not in merged:
            merged[key] = value
    return merged
