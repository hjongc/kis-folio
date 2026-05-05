.PHONY: test compile lint check smoke

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3.12)

test:
	$(PYTHON) -m pytest

compile:
	$(PYTHON) -X pycache_prefix=.pycache -m compileall src tests

lint:
	$(PYTHON) -m ruff check src tests

check: compile lint test

smoke:
	FOLIO_DB_PATH=$(PWD)/.folio-test/smoke.db PYTHONPATH=src $(PYTHON) -m folio.cli --env-file .env.example status --mock
	FOLIO_DB_PATH=$(PWD)/.folio-test/smoke.db PYTHONPATH=src $(PYTHON) -m folio.cli --env-file .env.example analyze --mock
