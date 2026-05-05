from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

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
        for run in workflow.agent_runs:
            run.id = save_agent_run(settings.db_path, run)
            saved_runs.append(run)
        write_text(paths.multi_agent_path, render_agent_runs_markdown(saved_runs))
        write_text(paths.workflow_trace_path, workflow.trace_markdown)
        write_text(paths.report_path, workflow.final_report)
        return ReportResult(paths=paths, usage=workflow.final_usage, agentic=True, no_llm=False)

    advisor = OpenAICompatibleAdvisor(settings.llm, repo_root)
    report_markdown, usage = advisor.generate_markdown_report(prompt=prompt, deep=request.deep)
    write_text(paths.report_path, report_markdown)
    return ReportResult(paths=paths, usage=usage, agentic=False, no_llm=False)


def write_text(path: Path, content: str) -> None:
    ensure_private_directory(path.parent)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)
