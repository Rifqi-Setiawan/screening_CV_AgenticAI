.PHONY: test lint typecheck run-api run-worker migrate

VENV = .venv

migrate:
	$(VENV)/bin/alembic upgrade head

test:
	$(VENV)/bin/pytest

lint:
	$(VENV)/bin/ruff check src tests

typecheck:
	$(VENV)/bin/mypy src tests

run-api:
	$(VENV)/bin/uvicorn src.api.main:app --host 127.0.0.1 --port 8111

run-worker:
	$(VENV)/bin/python -m src.worker.main
