.PHONY: test lint typecheck run-api run-worker eval seed clean migrate test-db

VENV = .venv
PYTHON = $(VENV)/bin/python
UVICORN = $(VENV)/bin/uvicorn
PYTEST = $(VENV)/bin/pytest
RUFF = $(VENV)/bin/ruff
MYPY = $(VENV)/bin/mypy
ALEMBIC = $(VENV)/bin/alembic

TEST_DB_NAME ?= cv_screening_test
TEST_DATABASE_URL ?= $(shell grep '^DATABASE_URL=' .env 2>/dev/null | cut -d= -f2- | sed 's|/cv_screening$$|/cv_screening_test|')

migrate:
	$(ALEMBIC) upgrade head

test-db:
	@echo "=== Provisioning $(TEST_DB_NAME) ==="
	@PYTHONPATH=. $(PYTHON) -c "import os, psycopg; from urllib.parse import urlparse; \
	raw = os.environ.get('TEST_DATABASE_URL') or '$(TEST_DATABASE_URL)'; \
	p = urlparse(raw); \
	m_url = p._replace(path='/postgres').geturl(); \
	conn = psycopg.connect(m_url, autocommit=True); \
	cur = conn.cursor(); \
	cur.execute('DROP DATABASE IF EXISTS $(TEST_DB_NAME);'); \
	cur.execute('CREATE DATABASE $(TEST_DB_NAME) OWNER cv_screening_user;'); \
	conn.close(); print('Created $(TEST_DB_NAME)')"
	@DATABASE_URL=$(TEST_DATABASE_URL) APP_ENV=test $(ALEMBIC) upgrade head
	@DATABASE_URL=$(TEST_DATABASE_URL) APP_ENV=test PYTHONPATH=. $(PYTHON) scripts/seed_users.py
	@echo "=== $(TEST_DB_NAME) Ready ==="

test:
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) PYTHONPATH=. $(PYTEST) -v

lint:
	$(RUFF) check src tests

format:
	$(RUFF) format src tests

typecheck:
	$(MYPY) src tests --ignore-missing-imports

run-api:
	$(UVICORN) src.api.main:app --host 127.0.0.1 --port 8110 --reload

run-worker:
	PYTHONPATH=. $(PYTHON) -m src.worker.main

seed:
	PYTHONPATH=. $(PYTHON) scripts/seed_users.py

CV_EXTRACTOR_PATH ?= /srv/hermes-control/services/cv-extractor/src

eval:
	cd docs/spec/golden_dataset && $(PYTHON) evaluate.py --self-test
	PYTHONPATH=$(CV_EXTRACTOR_PATH) $(PYTHON) scripts/m0_test_adapter.py
	$(PYTHON) docs/spec/golden_dataset/evaluate.py --extraction scripts/pred_extraction.json

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
