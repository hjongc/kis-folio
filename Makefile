.PHONY: test compile lint check smoke

test:
	python3 -m pytest

compile:
	python3 -X pycache_prefix=.pycache -m compileall src tests

lint:
	python3 -m ruff check src tests

check: compile lint test

smoke:
	FOLIO_DB_PATH=$(PWD)/.folio-test/smoke.db PYTHONPATH=src python3 -m folio.cli --env-file .env.example status --mock
	FOLIO_DB_PATH=$(PWD)/.folio-test/smoke.db PYTHONPATH=src python3 -m folio.cli --env-file .env.example analyze --mock
