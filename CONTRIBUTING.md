# Contributing

Thanks for considering a contribution.

## Project Scope

`kis-folio` is an unofficial local-first analysis tool for KIS OpenAPI account
data. Keep contributions within the read-only analysis scope unless the
maintainer explicitly changes the roadmap.

Out of scope by default:

- Order placement
- Automatic trading
- Hosted storage of user portfolios
- Committing real account reports or credentials

## Development Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
make check
```

Use mock data for tests and examples:

```bash
folio status --mock
folio report --mock --no-llm
```

## Commit Convention

Use Conventional Commits:

```text
type(scope): subject
```

Examples:

- `feat(agent): add workflow cost budget`
- `fix(kis): handle empty balance response`
- `docs(setup): clarify llm provider config`
- `test(agent): cover debate round ordering`

## Pull Request Checklist

- [ ] `make check` passes
- [ ] `make audit` passes
- [ ] New user-facing behavior is documented
- [ ] No credentials, real reports, DBs, or token files are included
- [ ] Investment advice language remains framed as decision support, not advice
