from __future__ import annotations

import operator
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated, Any, TypedDict

from .advisor import AdvisorError, OpenRouterAdvisor
from .config import OpenRouterSettings
from .models import AgentRun, Position, Snapshot, WorkflowEvent
from .reporting import infer_asset_class, safe_ratio, sorted_positions


@dataclass(frozen=True)
class LiquidityNeed:
    amount: float | None = None
    needed_by: date | None = None
    withdraw_by: date | None = None


@dataclass(frozen=True)
class AgentBrief:
    role: str
    stance: str
    findings: list[str]
    data_gaps: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentSpec:
    role: str
    stance: str
    task: str
    model_route: str = "fast"


@dataclass
class AgentWorkflowResult:
    engine: str
    agent_runs: list[AgentRun]
    final_report: str
    final_usage: dict[str, Any]
    trace_markdown: str


AGENT_SPECS = [
    AgentSpec(
        "Allocation Analyst",
        "계좌 구조와 비중 점검",
        "자산군, 현금, Top 포지션, 집중도를 분석하고 구조적 문제를 찾아라.",
        "fast",
    ),
    AgentSpec(
        "Macro Exposure Analyst",
        "매크로 민감도 점검",
        "국내/원화/ETF/레버리지/반도체 노출이 작성자 매크로 가설과 맞는지 분석하라.",
        "advisor",
    ),
    AgentSpec(
        "Market/Momentum Analyst",
        "가격 모멘텀 점검",
        "평가손익률, 상위/하위 포지션, 추세 추정과 데이터 한계를 분석하라.",
        "fast",
    ),
    AgentSpec(
        "Liquidity Planner",
        "현금 필요 제약",
        "필요 현금, 출금일, 현재 현금, 매도 필요 여부를 최상위 제약으로 분석하라.",
        "fast",
    ),
    AgentSpec(
        "Bull Researcher",
        "상승 시나리오",
        "작성자 가설이 맞을 때 어떤 보유 포지션이 수혜를 보는지 강한 논거를 제시하라.",
        "advisor",
    ),
    AgentSpec(
        "Bear Researcher",
        "하락 시나리오",
        "작성자 가설이 틀릴 때 계좌가 어떻게 손상되는지 반대 논거를 제시하라.",
        "advisor",
    ),
    AgentSpec(
        "Risk Manager",
        "자본 보존",
        "허용 drawdown, 집중도, 레버리지, 현금 잠금 관점에서 위험 한도를 제시하라.",
        "advisor",
    ),
]


DEBATE_SPECS = [
    AgentSpec(
        "Bull Researcher Rebuttal",
        "상승 논거 재검토",
        "초기 에이전트 결과를 보고 상승 시나리오에서 여전히 유효한 논거와 약해진 논거를 분리하라.",
        "advisor",
    ),
    AgentSpec(
        "Bear Researcher Rebuttal",
        "하락 논거 재검토",
        "초기 에이전트 결과를 보고 작성자의 가설이 틀릴 경우 가장 먼저 훼손될 지점을 제시하라.",
        "advisor",
    ),
    AgentSpec(
        "Risk Manager Final Review",
        "최종 위험 한도 검토",
        "초기 분석과 debate 결과를 보고 출금 전까지 반드시 지켜야 할 한도와 트리거를 제시하라.",
        "advisor",
    ),
]


class AgentWorkflowState(TypedDict, total=False):
    runs: Annotated[list[AgentRun], operator.add]
    events: Annotated[list[WorkflowEvent], operator.add]


def run_llm_agent_workflow(
    settings: OpenRouterSettings,
    repo_root: Path,
    account_id: str,
    snapshot: Snapshot,
    snapshot_markdown: str,
    deterministic_briefs_markdown: str,
    liquidity_need: LiquidityNeed,
    report_prompt: str,
    deep: bool = False,
    engine: str = "auto",
    debate_rounds: int = 1,
    max_retries: int = 2,
    max_workers: int = 4,
) -> AgentWorkflowResult:
    if engine not in {"auto", "langgraph", "local"}:
        raise ValueError("engine must be one of: auto, langgraph, local")
    selected_engine = engine
    if selected_engine == "auto":
        selected_engine = "langgraph" if langgraph_available() else "local"
    if selected_engine == "langgraph":
        try:
            runs, events = _run_langgraph_agent_workflow(
                settings=settings,
                repo_root=repo_root,
                account_id=account_id,
                snapshot=snapshot,
                snapshot_markdown=snapshot_markdown,
                deterministic_briefs_markdown=deterministic_briefs_markdown,
                liquidity_need=liquidity_need,
                deep=deep,
                debate_rounds=debate_rounds,
                max_retries=max_retries,
            )
        except ImportError:
            if engine == "langgraph":
                raise
            selected_engine = "local"
            runs, events = _run_local_agent_workflow(
                settings=settings,
                repo_root=repo_root,
                account_id=account_id,
                snapshot=snapshot,
                snapshot_markdown=snapshot_markdown,
                deterministic_briefs_markdown=deterministic_briefs_markdown,
                liquidity_need=liquidity_need,
                deep=deep,
                debate_rounds=debate_rounds,
                max_retries=max_retries,
                max_workers=max_workers,
            )
    else:
        runs, events = _run_local_agent_workflow(
            settings=settings,
            repo_root=repo_root,
            account_id=account_id,
            snapshot=snapshot,
            snapshot_markdown=snapshot_markdown,
            deterministic_briefs_markdown=deterministic_briefs_markdown,
            liquidity_need=liquidity_need,
            deep=deep,
            debate_rounds=debate_rounds,
            max_retries=max_retries,
            max_workers=max_workers,
        )

    report_markdown, usage, _agent_outputs = synthesize_llm_agent_report(
        settings=settings,
        repo_root=repo_root,
        snapshot_markdown=snapshot_markdown,
        deterministic_briefs_markdown=deterministic_briefs_markdown,
        agent_runs=runs,
        report_prompt=report_prompt,
        deep=deep,
    )
    events.append(
        WorkflowEvent(
            ts=datetime.now(tz=timezone.utc),
            node="Portfolio Manager Synthesis",
            status="ok",
            detail=f"final report generated with {usage.get('total_tokens', 'unknown')} tokens",
        )
    )
    return AgentWorkflowResult(
        engine=selected_engine,
        agent_runs=runs,
        final_report=report_markdown,
        final_usage=usage,
        trace_markdown=render_workflow_trace_markdown(selected_engine, events, runs, usage),
    )


def build_agent_briefs(
    snapshot: Snapshot,
    liquidity_need: LiquidityNeed | None = None,
) -> list[AgentBrief]:
    return [
        allocation_analyst(snapshot),
        macro_exposure_analyst(snapshot),
        momentum_analyst(snapshot),
        liquidity_analyst(snapshot, liquidity_need or LiquidityNeed()),
        bull_researcher(snapshot),
        bear_researcher(snapshot),
        risk_manager(snapshot),
        portfolio_manager(snapshot, liquidity_need or LiquidityNeed()),
        data_gap_analyst(),
    ]


def run_llm_agent_team(
    settings: OpenRouterSettings,
    repo_root: Path,
    account_id: str,
    snapshot: Snapshot,
    snapshot_markdown: str,
    deterministic_briefs_markdown: str,
    liquidity_need: LiquidityNeed,
    deep: bool = False,
) -> list[AgentRun]:
    advisor = OpenRouterAdvisor(settings, repo_root)
    runs: list[AgentRun] = []
    prior_outputs: list[str] = []
    for spec in AGENT_SPECS:
        model = choose_agent_model(settings, spec.model_route, deep=deep)
        prompt = render_agent_prompt(
            spec=spec,
            snapshot_markdown=snapshot_markdown,
            deterministic_briefs_markdown=deterministic_briefs_markdown,
            liquidity_need=liquidity_need,
            prior_outputs=prior_outputs,
        )
        output, usage = advisor.generate_markdown(
            system_prompt=agent_system_prompt(spec),
            user_prompt=prompt,
            model=model,
            operation=f"agent:{spec.role}",
            timeout=70,
        )
        run = AgentRun(
            id=None,
            account_id=account_id,
            snapshot_id=snapshot.id,
            ts=datetime.now(tz=timezone.utc),
            role=spec.role,
            model=model,
            input_json={
                "role": spec.role,
                "stance": spec.stance,
                "task": spec.task,
                "liquidity_need": liquidity_need_to_json(liquidity_need),
            },
            output_markdown=output,
            token_usage=usage,
        )
        runs.append(run)
        prior_outputs.append(f"## {spec.role}\n\n{output}")
    return runs


def langgraph_available() -> bool:
    try:
        import langgraph.graph  # noqa: F401
    except ImportError:
        return False
    return True


def _run_local_agent_workflow(
    settings: OpenRouterSettings,
    repo_root: Path,
    account_id: str,
    snapshot: Snapshot,
    snapshot_markdown: str,
    deterministic_briefs_markdown: str,
    liquidity_need: LiquidityNeed,
    deep: bool,
    debate_rounds: int,
    max_retries: int,
    max_workers: int,
) -> tuple[list[AgentRun], list[WorkflowEvent]]:
    advisor = OpenRouterAdvisor(settings, repo_root)
    events: list[WorkflowEvent] = [
        WorkflowEvent(
            ts=datetime.now(tz=timezone.utc),
            node="workflow",
            status="start",
            detail=f"engine=local, analyst_workers={max_workers}, debate_rounds={debate_rounds}",
        )
    ]
    runs: list[AgentRun] = []
    worker_count = max(1, min(max_workers, len(AGENT_SPECS)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(
                _run_single_agent_with_retry,
                advisor,
                settings,
                account_id,
                snapshot,
                snapshot_markdown,
                deterministic_briefs_markdown,
                liquidity_need,
                spec,
                [],
                deep,
                max_retries,
                0,
            ): spec
            for spec in AGENT_SPECS
        }
        for future in as_completed(futures):
            run, run_events = future.result()
            runs.append(run)
            events.extend(run_events)
    runs.sort(key=lambda run: [spec.role for spec in AGENT_SPECS].index(run.role))

    for round_no in range(1, max(debate_rounds, 0) + 1):
        prior_outputs = [f"## {run.role}\n\n{run.output_markdown}" for run in runs]
        for spec in DEBATE_SPECS:
            run, run_events = _run_single_agent_with_retry(
                advisor=advisor,
                settings=settings,
                account_id=account_id,
                snapshot=snapshot,
                snapshot_markdown=snapshot_markdown,
                deterministic_briefs_markdown=deterministic_briefs_markdown,
                liquidity_need=liquidity_need,
                spec=spec,
                prior_outputs=prior_outputs,
                deep=deep,
                max_retries=max_retries,
                debate_round=round_no,
            )
            runs.append(run)
            events.extend(run_events)
            prior_outputs.append(f"## {run.role}\n\n{run.output_markdown}")
    return runs, events


def _run_langgraph_agent_workflow(
    settings: OpenRouterSettings,
    repo_root: Path,
    account_id: str,
    snapshot: Snapshot,
    snapshot_markdown: str,
    deterministic_briefs_markdown: str,
    liquidity_need: LiquidityNeed,
    deep: bool,
    debate_rounds: int,
    max_retries: int,
) -> tuple[list[AgentRun], list[WorkflowEvent]]:
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise ImportError(
            "LangGraph is not installed. Install with `python -m pip install -e '.[agent]'` "
            "on Python 3.10+."
        ) from exc

    advisor = OpenRouterAdvisor(settings, repo_root)
    builder = StateGraph(AgentWorkflowState)

    def make_agent_node(spec: AgentSpec):
        def agent_node(state: AgentWorkflowState) -> AgentWorkflowState:
            del state
            run, events = _run_single_agent_with_retry(
                advisor=advisor,
                settings=settings,
                account_id=account_id,
                snapshot=snapshot,
                snapshot_markdown=snapshot_markdown,
                deterministic_briefs_markdown=deterministic_briefs_markdown,
                liquidity_need=liquidity_need,
                spec=spec,
                prior_outputs=[],
                deep=deep,
                max_retries=max_retries,
                debate_round=0,
            )
            return {"runs": [run], "events": events}

        return agent_node

    agent_node_names: list[str] = []
    for spec in AGENT_SPECS:
        node_name = node_name_for_role(spec.role)
        builder.add_node(node_name, make_agent_node(spec))
        builder.add_edge(START, node_name)
        agent_node_names.append(node_name)

    def debate_node(state: AgentWorkflowState) -> AgentWorkflowState:
        if debate_rounds <= 0:
            return {"runs": [], "events": []}
        runs = list(state.get("runs", []))
        debate_runs: list[AgentRun] = []
        events: list[WorkflowEvent] = []
        prior_outputs = [f"## {run.role}\n\n{run.output_markdown}" for run in runs]
        for round_no in range(1, debate_rounds + 1):
            for spec in DEBATE_SPECS:
                run, run_events = _run_single_agent_with_retry(
                    advisor=advisor,
                    settings=settings,
                    account_id=account_id,
                    snapshot=snapshot,
                    snapshot_markdown=snapshot_markdown,
                    deterministic_briefs_markdown=deterministic_briefs_markdown,
                    liquidity_need=liquidity_need,
                    spec=spec,
                    prior_outputs=prior_outputs,
                    deep=deep,
                    max_retries=max_retries,
                    debate_round=round_no,
                )
                debate_runs.append(run)
                events.extend(run_events)
                prior_outputs.append(f"## {run.role}\n\n{run.output_markdown}")
        return {"runs": debate_runs, "events": events}

    builder.add_node("debate_review", debate_node)
    builder.add_edge(agent_node_names, "debate_review")
    builder.add_edge("debate_review", END)
    graph = builder.compile()
    result = graph.invoke(
        {
            "runs": [],
            "events": [
                WorkflowEvent(
                    ts=datetime.now(tz=timezone.utc),
                    node="workflow",
                    status="start",
                    detail=f"engine=langgraph, analyst_nodes={len(agent_node_names)}",
                )
            ],
        }
    )
    return list(result.get("runs", [])), list(result.get("events", []))


def _run_single_agent_with_retry(
    advisor: OpenRouterAdvisor,
    settings: OpenRouterSettings,
    account_id: str,
    snapshot: Snapshot,
    snapshot_markdown: str,
    deterministic_briefs_markdown: str,
    liquidity_need: LiquidityNeed,
    spec: AgentSpec,
    prior_outputs: list[str],
    deep: bool,
    max_retries: int,
    debate_round: int,
) -> tuple[AgentRun, list[WorkflowEvent]]:
    events: list[WorkflowEvent] = []
    attempts = max(1, max_retries + 1)
    model = choose_agent_model(settings, spec.model_route, deep=deep)
    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        try:
            prompt = render_agent_prompt(
                spec=spec,
                snapshot_markdown=snapshot_markdown,
                deterministic_briefs_markdown=deterministic_briefs_markdown,
                liquidity_need=liquidity_need,
                prior_outputs=prior_outputs,
            )
            output, usage = advisor.generate_markdown(
                system_prompt=agent_system_prompt(spec),
                user_prompt=prompt,
                model=model,
                operation=f"agent:{spec.role}",
                timeout=90,
            )
            validate_agent_output(spec, output)
            duration = time.monotonic() - started
            events.append(
                WorkflowEvent(
                    ts=datetime.now(tz=timezone.utc),
                    node=spec.role,
                    status="ok",
                    detail=f"model={model}, debate_round={debate_round}",
                    attempt=attempt,
                    duration_sec=duration,
                )
            )
            return (
                AgentRun(
                    id=None,
                    account_id=account_id,
                    snapshot_id=snapshot.id,
                    ts=datetime.now(tz=timezone.utc),
                    role=spec.role,
                    model=model,
                    input_json={
                        "role": spec.role,
                        "stance": spec.stance,
                        "task": spec.task,
                        "liquidity_need": liquidity_need_to_json(liquidity_need),
                        "attempt": attempt,
                        "debate_round": debate_round,
                    },
                    output_markdown=output,
                    token_usage=usage,
                ),
                events,
            )
        except AdvisorError as exc:
            duration = time.monotonic() - started
            events.append(
                WorkflowEvent(
                    ts=datetime.now(tz=timezone.utc),
                    node=spec.role,
                    status="retry" if attempt < attempts else "error",
                    detail=str(exc),
                    attempt=attempt,
                    duration_sec=duration,
                )
            )
            if attempt >= attempts:
                raise
            time.sleep(min(2**attempt, 8))
    raise AdvisorError(f"{spec.role} failed without producing an output")


def validate_agent_output(spec: AgentSpec, output: str) -> None:
    if len(output.strip()) < 50:
        raise AdvisorError(f"{spec.role} returned an unexpectedly short output")


def node_name_for_role(role: str) -> str:
    return role.lower().replace("/", "_").replace(" ", "_")


def synthesize_llm_agent_report(
    settings: OpenRouterSettings,
    repo_root: Path,
    snapshot_markdown: str,
    deterministic_briefs_markdown: str,
    agent_runs: list[AgentRun],
    report_prompt: str,
    deep: bool = False,
) -> tuple[str, dict[str, Any], str]:
    advisor = OpenRouterAdvisor(settings, repo_root)
    model = settings.advisor_deep_model if deep else settings.advisor_model
    agent_outputs = render_agent_runs_markdown(agent_runs)
    prompt = (
        f"{report_prompt}\n\n"
        "multi_agent_outputs.md:\n\n"
        f"{agent_outputs}\n\n"
        "종합 지시:\n"
        "- 위 개별 에이전트 출력 사이의 충돌을 명시적으로 조정하라.\n"
        "- Portfolio Manager 관점에서 최종 리포트를 작성하라.\n"
        "- 주문 실행 지시는 금지하고, trigger/action/size 규칙으로만 표현하라.\n"
    )
    output, usage = advisor.generate_markdown(
        system_prompt=(
            "당신은 멀티에이전트 포트폴리오 리서치 팀의 Portfolio Manager다. "
            "각 에이전트의 의견을 종합하되, 투자 권유가 아니라 의사결정 보조 리포트를 작성한다."
        ),
        user_prompt=prompt,
        model=model,
        operation="agent:Portfolio Manager Synthesis",
        timeout=120,
    )
    return output, usage, agent_outputs


def render_agent_prompt(
    spec: AgentSpec,
    snapshot_markdown: str,
    deterministic_briefs_markdown: str,
    liquidity_need: LiquidityNeed,
    prior_outputs: list[str],
) -> str:
    prior = "\n\n".join(prior_outputs) if prior_outputs else "없음"
    return f"""역할: {spec.role}
관점: {spec.stance}
작업: {spec.task}

출력 규칙:
- 5개 이하 bullet로 핵심 발견을 작성한다.
- 데이터가 없으면 반드시 "데이터 부족"이라고 쓴다.
- 필요한 경우 trigger/action/size 형태의 실행 규칙을 제안한다.
- 신규 종목 매수 권유는 하지 않는다.
- 다른 에이전트와 토론할 수 있도록 결론과 근거를 분리한다.

liquidity_need:
{liquidity_need_to_json(liquidity_need)}

portfolio_snapshot.md:
{snapshot_markdown}

deterministic_agent_briefs.md:
{deterministic_briefs_markdown}

prior_agent_outputs.md:
{prior}
"""


def agent_system_prompt(spec: AgentSpec) -> str:
    return (
        f"당신은 folio 멀티에이전트 팀의 {spec.role}다. "
        f"관점은 '{spec.stance}'이다. "
        "한국 개인투자자의 계좌 단위 리포트를 위해 사실과 해석을 분리해 분석한다."
    )


def choose_agent_model(settings: OpenRouterSettings, route: str, deep: bool = False) -> str:
    if deep:
        return settings.advisor_deep_model
    if route == "fast":
        return settings.fast_model
    return settings.advisor_model


def render_agent_runs_markdown(runs: list[AgentRun]) -> str:
    lines = [
        "---",
        "type: multi-agent-runs",
        "schema_version: 1.0",
        "---",
        "",
        "# Multi-Agent Runs",
    ]
    for run in runs:
        lines.extend(
            [
                "",
                f"## {run.role}",
                "",
                f"- model: `{run.model}`",
                f"- token_usage: `{run.token_usage}`",
                "",
                run.output_markdown.strip(),
            ]
        )
    return "\n".join(lines) + "\n"


def render_workflow_trace_markdown(
    engine: str,
    events: list[WorkflowEvent],
    runs: list[AgentRun],
    final_usage: dict[str, Any],
) -> str:
    total_tokens = sum(int(run.token_usage.get("total_tokens", 0) or 0) for run in runs)
    total_tokens += int(final_usage.get("total_tokens", 0) or 0)
    total_cost = sum(float(run.token_usage.get("cost", 0) or 0) for run in runs)
    total_cost += float(final_usage.get("cost", 0) or 0)
    lines = [
        "---",
        "type: portfolio-workflow-trace",
        "schema_version: 1.0",
        f"engine: {engine}",
        "---",
        "",
        "# Portfolio Workflow Trace",
        "",
        "## Summary",
        "",
        f"- engine: `{engine}`",
        f"- agent_runs: {len(runs)}",
        f"- total_tokens_reported: {total_tokens}",
        f"- total_cost_reported: {total_cost:.6f}",
        "",
        "## Events",
        "",
        "| ts | node | status | attempt | duration_sec | detail |",
        "|---|---|---|---:|---:|---|",
    ]
    for event in events:
        detail = event.detail.replace("|", "/")
        lines.append(
            f"| {event.ts.isoformat()} | {event.node} | {event.status} | "
            f"{event.attempt} | {event.duration_sec:.2f} | {detail} |"
        )
    return "\n".join(lines) + "\n"


def liquidity_need_to_json(need: LiquidityNeed) -> dict[str, Any]:
    return {
        "amount": need.amount,
        "needed_by": need.needed_by.isoformat() if need.needed_by else None,
        "withdraw_by": need.withdraw_by.isoformat() if need.withdraw_by else None,
    }


def allocation_analyst(snapshot: Snapshot) -> AgentBrief:
    balance = snapshot.balance
    asset_total = balance.asset_total
    asset_amounts: dict[str, float] = {}
    for position in balance.positions:
        asset_class = infer_asset_class(position)
        asset_amounts[asset_class] = asset_amounts.get(asset_class, 0.0) + position.eval_amount
    findings = [
        f"총자산 {asset_total:,.0f}원 중 현금 {balance.cash:,.0f}원"
        f"({safe_ratio(balance.cash, asset_total):.1%})이다.",
        "자산군 비중: "
        + ", ".join(
            f"{name} {safe_ratio(amount, asset_total):.1%}"
            for name, amount in sorted(asset_amounts.items())
        ),
        f"Top 3 포지션 비중은 투자자산 기준 {snapshot.metrics.top_n_pct:.1%}, "
        f"HHI는 {snapshot.metrics.hhi:.3f}이다.",
    ]
    return AgentBrief("Allocation Analyst", "구조 점검", findings)


def macro_exposure_analyst(snapshot: Snapshot) -> AgentBrief:
    balance = snapshot.balance
    asset_total = balance.asset_total
    etf_amount = sum(
        position.eval_amount
        for position in balance.positions
        if infer_asset_class(position) == "ETF"
    )
    leverage_amount = sum(
        position.eval_amount for position in balance.positions if is_leverage_position(position)
    )
    semiconductor_amount = sum(
        position.eval_amount
        for position in balance.positions
        if has_any(position, ["반도체", "005930", "000660", "필라델피아"])
    )
    findings = [
        "국내 원화 자산 비중은 현재 입력 데이터 기준 100.0%이다.",
        f"ETF 비중은 총자산 기준 {safe_ratio(etf_amount, asset_total):.1%}이다.",
        f"레버리지 명목 비중은 총자산 기준 {safe_ratio(leverage_amount, asset_total):.1%}이며, "
        "기초지수 변동에 대한 실질 민감도는 이보다 크다.",
        "반도체 직접/테마 노출은 총자산 기준 약 "
        f"{safe_ratio(semiconductor_amount, asset_total):.1%}이다.",
    ]
    gaps = [
        "KIS 현재 잔고/시세만으로는 미국 M2, 전쟁/지정학 뉴스, "
        "외국인 수급 추세를 직접 검증할 수 없다.",
        "ETF 내부 구성 종목과 환헤지 여부는 상품 상세 데이터가 없으면 제한적으로만 추정된다.",
    ]
    return AgentBrief("Macro Exposure Analyst", "매크로 민감도 점검", findings, gaps)


def momentum_analyst(snapshot: Snapshot) -> AgentBrief:
    winners = sorted_positions(snapshot.balance.positions)[:3]
    by_return = sorted(
        snapshot.balance.positions, key=lambda position: position.pnl_pct, reverse=True
    )
    top_winners = by_return[:3]
    top_losers = list(reversed(by_return[-3:]))
    findings = [
        "평가금액 상위 포지션: "
        + ", ".join(f"{position.name} {position.eval_amount:,.0f}원" for position in winners),
        "손익률 상위: "
        + ", ".join(f"{position.name} {position.pnl_pct:+.1f}%" for position in top_winners),
        "손익률 하위: "
        + ", ".join(f"{position.name} {position.pnl_pct:+.1f}%" for position in top_losers),
    ]
    gaps = [
        "KIS 일별 차트 어댑터는 준비됐지만, 기본 리포트 입력에는 아직 "
        "20/60일 추세, 변동성, MDD 계산이 연결되지 않았다."
    ]
    return AgentBrief("Market/Momentum Analyst", "가격 모멘텀 점검", findings, gaps)


def liquidity_analyst(snapshot: Snapshot, need: LiquidityNeed) -> AgentBrief:
    balance = snapshot.balance
    findings = [f"현재 현금은 {balance.cash:,.0f}원이다."]
    gaps: list[str] = []
    if need.amount is None:
        gaps.append("필요 현금 금액이 입력되지 않아 출금 부족분을 계산할 수 없다.")
    else:
        shortage = max(need.amount - balance.cash, 0.0)
        findings.append(f"입력된 필요 현금은 {need.amount:,.0f}원, 부족분은 {shortage:,.0f}원이다.")
        if shortage <= 0:
            findings.append("현재 현금만으로 입력된 필요 금액을 충족한다.")
        else:
            findings.append("부족분은 결제 지연을 감안해 매도 마감일 전 확정해야 한다.")
    if need.needed_by:
        findings.append(f"필요일: {need.needed_by.isoformat()}")
    if need.withdraw_by:
        findings.append(f"출금 목표일: {need.withdraw_by.isoformat()}")
    gaps.append("KIS 휴장일/결제일 API를 연결하면 T+2 기반 최종 매도 가능일을 자동 산출할 수 있다.")
    return AgentBrief("Liquidity Planner", "현금 필요 제약", findings, gaps)


def bull_researcher(snapshot: Snapshot) -> AgentBrief:
    best = max(snapshot.balance.positions, key=lambda position: position.pnl_pct)
    findings = [
        f"가장 강한 근거는 {best.name}의 누적 손익률 {best.pnl_pct:+.1f}%이다.",
        "현금 비중이 높아 하락 시 재배분 여력이 있다.",
        "작성자 가설처럼 단기 국내 증시 강세가 이어지면 "
        "레버리지/반도체 노출이 성과를 키울 수 있다.",
    ]
    return AgentBrief("Bull Researcher", "상승 시나리오", findings)


def bear_researcher(snapshot: Snapshot) -> AgentBrief:
    leverage_weight = sum(
        snapshot.metrics.position_weights.get(position.code, 0.0)
        for position in snapshot.balance.positions
        if is_leverage_position(position)
    )
    worst = min(snapshot.balance.positions, key=lambda position: position.pnl_pct)
    findings = [
        f"레버리지 ETF 합산 비중은 투자자산 기준 {leverage_weight:.1%}이다.",
        f"가장 약한 포지션은 {worst.name}({worst.pnl_pct:+.1f}%)이다.",
        "국내/원화/테마 집중 때문에 외국인 수급 반전이나 반도체 조정에 동시 노출될 수 있다.",
    ]
    return AgentBrief("Bear Researcher", "하락 시나리오", findings)


def risk_manager(snapshot: Snapshot) -> AgentBrief:
    over_15 = [
        position
        for position in snapshot.balance.positions
        if safe_ratio(position.eval_amount, snapshot.balance.asset_total) > 0.15
    ]
    findings = [
        f"HHI {snapshot.metrics.hhi:.3f}; Top 3 {snapshot.metrics.top_n_pct:.1%}.",
        "총자산 기준 15% 초과 포지션: "
        + (", ".join(position.code for position in over_15) if over_15 else "없음"),
        "리스크 판단은 명목 비중과 레버리지 감안 실질 익스포저를 분리해야 한다.",
    ]
    return AgentBrief("Risk Manager", "자본 보존", findings)


def portfolio_manager(snapshot: Snapshot, need: LiquidityNeed) -> AgentBrief:
    findings = [
        "주문 기능은 의도적으로 없다. 이 브리프는 실행 전 점검용이다.",
        "보고서는 신규 종목 추천보다 보유 포지션의 비중 상한, "
        "현금 잠금, 가설 무효화 조건을 우선해야 한다.",
    ]
    if need.amount is not None:
        findings.append(
            "필요 현금은 투자 가능 현금에서 분리해 리포트 전체의 최상위 제약으로 다룬다."
        )
    return AgentBrief("Portfolio Manager", "최종 제약 통합", findings)


def data_gap_analyst() -> AgentBrief:
    return AgentBrief(
        role="Data Gap Analyst",
        stance="추가 데이터 요구",
        findings=[
            "KIS만으로 계좌 잔고, 현재가, KRX 업종, 일부 일별 차트/휴장일 데이터는 확보 가능하다.",
            "계좌 단위 매크로 리포트에는 외부 매크로/뉴스/수급/ETF 구성 데이터가 "
            "추가되면 품질이 크게 올라간다.",
        ],
        data_gaps=[
            "미국 M2/금리/달러 인덱스 API",
            "전쟁/지정학 뉴스 검색 API",
            "KOSPI/KOSDAQ 지수와 외국인 수급 시계열",
            "ETF 구성 종목, 레버리지 배율, 환헤지 여부",
            "거래내역/입출금/배당/세금 데이터",
        ],
    )


def render_agent_briefs_markdown(briefs: list[AgentBrief]) -> str:
    sections = [
        "---",
        "type: portfolio-agent-briefs",
        "inspired_by: TradingAgents",
        "scope: account-level-report",
        "schema_version: 1.0",
        "---",
        "",
        "# Portfolio Agent Briefs",
        "",
        "> TradingAgents의 티커 단위 analyst/research/risk 흐름을 "
        "계좌 단위로 변환한 KIS 기반 브리프.",
    ]
    for brief in briefs:
        sections.extend(
            ["", f"## {brief.role}", "", f"**stance**: {brief.stance}", "", "findings:"]
        )
        sections.extend(f"- {finding}" for finding in brief.findings)
        if brief.data_gaps:
            sections.extend(["", "data_gaps:"])
            sections.extend(f"- {gap}" for gap in brief.data_gaps)
    return "\n".join(sections) + "\n"


def is_leverage_position(position: Position) -> bool:
    return "레버리지" in position.name


def has_any(position: Position, needles: list[str]) -> bool:
    haystack = f"{position.code} {position.name} {position.sector}"
    return any(needle in haystack for needle in needles)
