# kis-folio

`kis-folio` is an unofficial local-first portfolio analysis tool for Korea
Investment Securities OpenAPI domestic-stock accounts. It reads KIS OpenAPI
account data, computes portfolio metrics, runs optional LangGraph multi-agent
LLM analysis through an OpenAI-compatible provider, and stores snapshots in
SQLite.

This project is not affiliated with Korea Investment & Securities Co., Ltd.
It intentionally avoids order placement and automatic trading. The scope is
read-only analysis, reporting, and decision support.

![kis-folio workflow](docs/assets/workflow.svg)

## Safety Notice

This is not financial advice. Generated reports are LLM-assisted decision
support and can be wrong. You are responsible for your own investment decisions,
API credentials, LLM provider privacy settings, and usage costs.

## Quick Start With Mock Data

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
folio status --mock
folio report --mock --no-llm --period 2026-05
```

This path uses no real brokerage credentials and makes no LLM call.

## Setup For Real Use

You can either run the guided setup:

```bash
folio setup
folio doctor
```

or edit `.env` manually.

1. Copy the environment template:

```bash
cp .env.example .env
```

2. Fill in KIS credentials:

```bash
KIS_APP_KEY_MAIN=your_kis_app_key
KIS_APP_SECRET_MAIN=your_kis_app_secret
KIS_CANO_MAIN=12345678
KIS_ACNT_PRDT_CD_MAIN=01
```

3. Configure an LLM provider.

OpenRouter is the default, but any OpenAI-compatible chat completions endpoint
can be used:

```bash
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-your-key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL_ADVISOR=anthropic/claude-sonnet-4.6
LLM_MODEL_FAST=anthropic/claude-haiku-4.5
```

For OpenAI-compatible self-hosted gateways, point `LLM_BASE_URL` at your gateway
and use model names supported by that gateway.

4. Initialize local state and validate configuration:

```bash
folio doctor
folio init-db
folio account add --id main --label "Main" --cano 12345678 --product-code 01
folio doctor --network
```

### `.env` Reference

| Variable | Required | Purpose |
|---|---|---|
| `FOLIO_DB_PATH` | No | Local SQLite path. Default: `~/.folio/folio.db` |
| `FOLIO_TOKEN_CACHE_PATH` | No | Local KIS token cache path |
| `KIS_BASE_URL` | Yes | KIS OpenAPI base URL |
| `KIS_APP_KEY_MAIN` | Yes | KIS app key |
| `KIS_APP_SECRET_MAIN` | Yes | KIS app secret |
| `KIS_CANO_MAIN` | Yes | 8-digit account prefix |
| `KIS_ACNT_PRDT_CD_MAIN` | Yes | Product code, usually `01` |
| `KIS_HTS_ID` | Sometimes | HTS ID if required for your KIS app |
| `LLM_PROVIDER` | Yes | Provider label, default `openrouter` |
| `LLM_API_KEY` | Yes for LLM calls | LLM provider API key |
| `LLM_BASE_URL` | Yes for LLM calls | OpenAI-compatible `/chat/completions` API base |
| `LLM_MODEL_ADVISOR` | Yes for LLM calls | Main report model |
| `LLM_MODEL_FAST` | Yes for agentic calls | Lower-cost model for lightweight agents |
| `LLM_MAX_CALLS` | No | Hard cap for agentic report LLM calls |
| `LLM_MAX_COST_USD` | No | Hard cap for provider-reported cost |
| `LLM_MAX_OUTPUT_TOKENS` | No | Per-agent completion cap |
| `LLM_MAX_REPORT_TOKENS` | No | Final synthesis completion cap |

`folio setup` writes these values interactively and hides secret input.

## Common Commands

```bash
folio status --mock
folio analyze --mock
folio report --mock --no-llm
folio status
folio analyze
folio
```

Use `--mock` until KIS credentials are issued and confirmed. Before real use,
run `folio doctor --network`, then `folio status`, then `folio analyze`.

## Workflow

1. Read KIS balance and current price data.
2. Build a fact-only `portfolio_snapshot.md`.
3. Compute deterministic allocation, concentration, and risk briefs.
4. Optionally run LangGraph agents:
   - initial analyst fan-out
   - bounded bull/bear/risk debate review
   - final Portfolio Manager synthesis
5. Write local markdown/SVG outputs under `reports/<YYYY-MM>/`.

The graph is bounded. `--debate-rounds` controls the number of review rounds,
and `LLM_MAX_CALLS` prevents accidental unbounded LLM usage.

## Reports

Generate a fact-only portfolio snapshot:

```bash
folio report --no-llm
```

Generate an advanced lens-based analysis report:

```bash
folio report
```

Generate a LangGraph multi-agent LLM report:

```bash
folio report --agentic
```

`--agentic` runs a LangGraph workflow: analyst fan-out, optional bull/bear/risk
debate review, and final Portfolio Manager synthesis. The project targets
Python 3.12.

Outputs are written under `reports/<YYYY-MM>/`:

- `portfolio_snapshot.md`: fact-only input data
- `portfolio_agent_briefs.md`: TradingAgents-inspired account-level analyst briefs
- `portfolio_multi_agent_runs.md`: role-by-role LLM outputs when `--agentic` is used
- `portfolio_workflow_trace.md`: workflow engine, retries, timing, and token/cost totals
- `portfolio_visual.svg`: lightweight visual summary
- `portfolio_analysis_report.md`: LLM report

For liquidity-constrained reports:

```bash
folio report --cash-need 50000000 --needed-by 2026-05-28 --withdraw-by 2026-05-25
```

Useful production controls:

```bash
folio report --agentic --agent-engine langgraph --debate-rounds 1 --agent-retries 2 --llm-max-calls 12 --llm-max-cost-usd 0.50
```

Cost and context limits can also be configured in `.env`:

```bash
LLM_MAX_CALLS=12
LLM_MAX_COST_USD=0.50
LLM_MAX_OUTPUT_TOKENS=1600
LLM_MAX_REPORT_TOKENS=5000
LLM_MAX_AGENT_OUTPUT_CHARS=5000
```

## Open Source Hygiene

Before publishing or opening a pull request:

```bash
make check
make audit
git status --short --ignored
```

Tracked files should never include `.env`, `.folio-test/`, `reports/`, SQLite
databases, token caches, or real account exports.

Git commits use Conventional Commits: `type(scope): subject`, for example
`feat(agent): add langgraph workflow`.

## License

MIT. See [LICENSE](LICENSE).
