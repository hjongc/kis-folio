# Production Runbook

`folio` is deployed as a local CLI/TUI package on the machine that owns the KIS
and OpenRouter credentials.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
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

## Multi-Agent Workflow

`folio report --agentic` executes:

1. Analyst fan-out: allocation, macro, momentum, liquidity, bull, bear, and risk agents.
2. Debate/review: bull rebuttal, bear rebuttal, and final risk review for each debate round.
3. Portfolio Manager synthesis: one final model call over all agent outputs.

The default engine is `auto`. It uses LangGraph when installed, otherwise the
local DAG executor. Latest LangGraph releases require Python 3.10+, while the
current local runtime is Python 3.9-compatible.

```bash
python3 -m pip install -e ".[agent,dev]"
folio report --agentic --agent-engine langgraph
```

Production controls:

- `--debate-rounds N`: number of bull/bear/risk review rounds. Default: `1`.
- `--agent-retries N`: retry count per agent node after a failed LLM call. Default: `2`.
- `--agent-workers N`: local executor parallelism for the initial analyst fan-out. Default: `4`.
- `--deep`: route all agents to the deep model.

The workflow trace records engine selection, node attempts, duration, and
reported token/cost totals. Agent outputs are stored in SQLite `agent_runs` and
also rendered to `portfolio_multi_agent_runs.md`.

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
