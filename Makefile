.PHONY: test compile lint check audit smoke

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3.12)

test:
	$(PYTHON) -m pytest

compile:
	$(PYTHON) -X pycache_prefix=.pycache -m compileall src tests

lint:
	$(PYTHON) -m ruff check src tests

check: compile lint test

audit:
	$(PYTHON) scripts/secret_audit.py

smoke:
	FOLIO_DB_PATH=$(PWD)/.folio-test/smoke.db PYTHONPATH=src $(PYTHON) -m folio.cli --env-file .env.example status --mock
	FOLIO_DB_PATH=$(PWD)/.folio-test/smoke.db PYTHONPATH=src $(PYTHON) -m folio.cli --env-file .env.example analyze --mock
	FOLIO_DB_PATH=$(PWD)/.folio-test/smoke.db PYTHONPATH=src $(PYTHON) -m folio.cli --env-file .env.example report --mock --no-llm --period 2026-05 --report-date 2026-05-05 --output-dir $(PWD)/.folio-test/smoke-reports
	PYTHONPATH=src $(PYTHON) -m folio.cli tui --help
