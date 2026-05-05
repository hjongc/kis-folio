# Security Policy

## Supported Versions

This project is pre-1.0. Security fixes target the `main` branch.

## Reporting a Vulnerability

Do not open public issues that include API keys, account numbers, access tokens,
portfolio reports, or other private financial data.

Use a private channel with the maintainer first. If no private contact is
available yet, open a public issue with only a high-level description and ask
for a private disclosure path.

## Data Handling

`kis-folio` is designed as a local-first, read-only portfolio analysis tool.

- KIS credentials must be stored in `.env`, which is ignored by Git.
- KIS access tokens are cached locally and ignored by Git.
- SQLite databases and generated reports are ignored by Git.
- LLM prompts may include holdings and cash balances. Choose your LLM provider
  and privacy settings accordingly.
- The project intentionally does not implement order placement.

## Maintainer Checklist Before Public Releases

Run:

```bash
make check
make audit
git status --short --ignored
```

Confirm that only source, tests, docs, and safe configuration templates are
tracked. Never commit `.env`, `.folio-test/`, `reports/`, SQLite DBs, token
caches, or real account exports.
