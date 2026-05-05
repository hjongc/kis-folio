# Production Runbook

`kis-folio` is deployed as a local CLI/TUI package on the machine that owns the
KIS and LLM provider credentials.

## Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

Fill `.env`, then run:

```bash
folio doctor
folio init-db
folio account add --id main --label Main --cano <CANO> --product-code <ACNT_PRDT_CD>
folio status
folio analyze
folio report
```

## Gates

Run before using against the real account:

```bash
make check
make smoke
folio doctor
```

`folio doctor --network` additionally validates KIS token issuance. It makes a
real network call to the production KIS API.

## Local State

- DB: `~/.folio/folio.db`
- KIS token cache: `~/.folio/kis_token.json`
- Both files are forced to owner-only permissions.

If KIS balance retrieval fails, `status`, `analyze`, and the TUI attempt to use
the latest saved snapshot for read-only fallback display/analysis.

## Monthly Reporting

```bash
folio report --period 2026-05
```

This writes:

- `reports/2026-05/portfolio_snapshot.md`
- `reports/2026-05/portfolio_agent_briefs.md`
- `reports/2026-05/portfolio_multi_agent_runs.md` when `--agentic` is used
- `reports/2026-05/portfolio_workflow_trace.md` when `--agentic` is used
- `reports/2026-05/portfolio_visual.svg`
- `reports/2026-05/portfolio_analysis_report.md`

Use `--no-llm` to generate only the fact snapshot without an OpenRouter call.
Use `--agentic` to run role-by-role LLM agents before final synthesis.

## LLM Providers

The client uses an OpenAI-compatible `/chat/completions` API. OpenRouter is the
default, but users can choose another compatible gateway:

```bash
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-your-key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL_ADVISOR=anthropic/claude-sonnet-4.6
LLM_MODEL_FAST=anthropic/claude-haiku-4.5
```

Cost controls:

```bash
LLM_MAX_CALLS=12
LLM_MAX_COST_USD=0.50
LLM_MAX_OUTPUT_TOKENS=1600
LLM_MAX_REPORT_TOKENS=5000
LLM_MAX_AGENT_OUTPUT_CHARS=5000
```

`LLM_MAX_COST_USD` depends on provider-reported `usage.cost`. If a provider does
not report cost, rely on call and token limits.

## Multi-Agent Workflow

`folio report --agentic` executes:

1. Analyst fan-out: allocation, macro, momentum, liquidity, bull, bear, and risk agents.
2. Debate/review: bull rebuttal, bear rebuttal, and final risk review for each debate round.
3. Portfolio Manager synthesis: one final model call over all agent outputs.

The default engine is `langgraph`. The project targets Python 3.12 and includes
LangGraph as a required dependency. The local DAG executor remains available for
offline diagnostics only.

```bash
python3.12 -m pip install -e ".[dev]"
folio report --agentic --agent-engine langgraph
```

Production controls:

- `--debate-rounds N`: number of bull/bear/risk review rounds. Default: `1`.
- `--agent-retries N`: retry count per agent node after a failed LLM call. Default: `2`.
- `--agent-workers N`: local executor parallelism when `--agent-engine local` is used. Default: `4`.
- `--llm-max-calls N`: CLI override for the LLM call cap.
- `--llm-max-cost-usd N`: CLI override for the reported cost cap.
- `--deep`: route all agents to the deep model.

The workflow trace records engine selection, node attempts, duration, and
reported token/cost totals. Agent outputs are stored in SQLite `agent_runs` and
also rendered to `portfolio_multi_agent_runs.md`.

## Git Convention

Commits use Conventional Commits:

```text
type(scope): subject
```

Examples:

- `feat(agent): add langgraph workflow`
- `chore(runtime): require python 3.12`
- `test(report): cover workflow trace rendering`

To reflect cash needs:

```bash
folio report --period 2026-05 --cash-need 50000000 --needed-by 2026-05-28 --withdraw-by 2026-05-25
```

## Data Coverage

Currently covered from KIS:

- Account balance and cash
- Current holdings, quantity, average price, current price, PnL
- KRX industry name via current price enrichment
- Daily OHLCV adapter for future technical indicators

Still missing for stronger account-level macro reports:

- Macro time series such as U.S. M2, policy rates, USD/KRW
- News/geopolitical search
- Foreign/institutional flow time series
- ETF holdings, leverage ratio, hedge status
- Transactions, deposits/withdrawals, dividends, realized tax lots
