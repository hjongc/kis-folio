# Open Source Readiness

## Branding

Recommended public repository name: `kis-folio`.

Rationale:

- `kis` signals Korea Investment Securities OpenAPI compatibility.
- `folio` keeps the product identity focused on portfolio analysis, not trading.
- The README and package metadata must state that this project is unofficial
  and not affiliated with Korea Investment & Securities Co., Ltd.

Avoid:

- Using KIS logos, screenshots, or brand assets.
- Naming the project as if it were an official KIS product.
- Publishing real account screenshots, reports, or logs.

## License

License: MIT.

Rationale:

- Simple and familiar for individual open-source users.
- Low friction for personal local tools.
- Compatible with most downstream use cases.

If future hosted or commercial features are added, revisit the license before
launching those features.

## Public Release Gate

Before making the GitHub repository public:

```bash
make check
make audit
git status --short --ignored
git log --oneline --all
```

Manual checks:

- `.env` is ignored and not in Git history.
- `.folio-test/`, `reports/`, DB files, and token caches are ignored.
- README examples use mock data or placeholders only.
- No generated real portfolio report is tracked.
- KIS/OpenRouter/LLM provider terms are linked, not copied.
- Disclaimer says the tool is not financial advice and has no order execution.

## Known Limitations to Disclose

- Current KIS adapter covers domestic account balance and price enrichment.
- Transactions, deposits/withdrawals, dividends, and tax lots are not complete.
- LLM providers may process holdings/cash data. Users must choose providers and
  privacy settings deliberately.
- Agentic reports can cost money. Defaults include call and output-token limits,
  but users should still set `LLM_MAX_COST_USD` for hard cost control.
