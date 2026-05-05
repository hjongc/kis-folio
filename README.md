# folio

`folio` is a local, single-user portfolio analysis tool for Korea Investment
Securities domestic-stock accounts. It reads KIS OpenAPI account data, computes
portfolio metrics, asks an OpenRouter-hosted LLM for conservative review cards,
and stores snapshots in SQLite.

Phase 1 intentionally avoids any trading capability. It only implements
authentication, balance/price reads, analysis, advisor output persistence, and a
Textual dashboard with a plain terminal fallback.

## Setup

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Fill `.env` with issued KIS production keys and an OpenRouter API key.

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

Generate a true multi-agent LLM report:

```bash
folio report --agentic
```

Outputs are written under `reports/<YYYY-MM>/`:

- `portfolio_snapshot.md`: fact-only input data
- `portfolio_agent_briefs.md`: TradingAgents-inspired account-level analyst briefs
- `portfolio_multi_agent_runs.md`: role-by-role LLM outputs when `--agentic` is used
- `portfolio_visual.svg`: lightweight visual summary
- `portfolio_analysis_report.md`: OpenRouter LLM report

For liquidity-constrained reports:

```bash
folio report --cash-need 50000000 --needed-by 2026-05-28 --withdraw-by 2026-05-25
```
