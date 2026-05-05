# kis-folio

`kis-folio` is an unofficial local-first portfolio analysis tool for Korea
Investment Securities OpenAPI domestic-stock accounts. It reads KIS OpenAPI
account data, computes portfolio metrics, runs optional LangGraph multi-agent
LLM analysis through an OpenAI-compatible provider, and stores snapshots in
SQLite.

This project is not affiliated with Korea Investment & Securities Co., Ltd.
It intentionally avoids order placement and automatic trading. The scope is
read-only analysis, reporting, and decision support.

## Safety Notice

This is not financial advice. Generated reports are LLM-assisted decision
support and can be wrong. You are responsible for your own investment decisions,
API credentials, LLM provider privacy settings, and usage costs.

## Setup

```bash
cp .env.example .env
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Fill `.env` with issued KIS production keys and your preferred LLM provider key.
OpenRouter is the default, but any OpenAI-compatible chat completions endpoint
can be used by setting:

```bash
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-your-key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL_ADVISOR=anthropic/claude-sonnet-4.6
LLM_MODEL_FAST=anthropic/claude-haiku-4.5
```

For OpenAI-compatible self-hosted gateways, point `LLM_BASE_URL` at your gateway
and use model names supported by that gateway.

## Commands

```bash
folio doctor
folio init-db
folio account add --id main --label "Main" --cano 12345678 --product-code 01
folio status --mock
folio analyze --mock
folio report --mock --no-llm
folio
```

Use `--mock` until KIS credentials are issued and confirmed. Before real use,
run `folio doctor --network`, then `folio status`, then `folio analyze`.

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
