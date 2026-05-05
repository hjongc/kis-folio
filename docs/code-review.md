# Code Review Notes

## Security

- Good: `.env`, local DBs, token caches, and generated reports are ignored.
- Good: KIS token cache files are written with owner-only permissions.
- Good: current scope is read-only and does not implement order APIs.
- Risk: LLM prompts include holdings and cash balances. Mitigation: configurable
  OpenAI-compatible provider, privacy note, and cost/context limits.
- Risk: local generated reports can contain private financial data. Mitigation:
  `reports/` remains ignored and `make audit` scans tracked files.

## Stability

- KIS live fetch falls back to the latest saved snapshot for read-only display
  and analysis when possible.
- LangGraph workflow has a fixed topology:
  1. analyst fan-out
  2. bounded debate/review rounds
  3. final Portfolio Manager synthesis
- There is no unbounded graph cycle. Debate rounds are controlled by
  `--debate-rounds`.
- Agent outputs are sorted by role order before synthesis so parallel fan-out
  does not create nondeterministic report ordering.

## Cost Control

- `LLM_MAX_CALLS` rejects workflows that would exceed the configured number of
  calls before any LLM request is made.
- `LLM_MAX_OUTPUT_TOKENS` caps per-agent completions.
- `LLM_MAX_REPORT_TOKENS` caps final synthesis completions.
- `LLM_MAX_AGENT_OUTPUT_CHARS` clips agent outputs before final synthesis.
- `LLM_MAX_COST_USD` stops the workflow once reported provider cost exceeds the
  configured threshold. Providers that do not report cost cannot be fully
  controlled by this setting, so call and token caps remain the primary guard.

## Functional Gaps

- Transaction history, deposits/withdrawals, dividends, realized PnL, and tax
  lots are not fully integrated.
- Benchmark and macro data are mostly user-provided or missing.
- ETF holdings, leverage ratio, and hedge status are not yet ingested from a
  trusted source.
- Calendar-aware T+2 settlement planning is still a data gap.

## Recommended Next Hardening

- Add CI secret scanning with a dedicated tool such as gitleaks.
- Add typed provider adapters if non-OpenAI-compatible LLM APIs are needed.
- Add structured JSON output validation for agent runs.
- Add snapshot fixture tests for larger real-world account shapes without real
  financial data.
