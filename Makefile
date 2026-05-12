.PHONY: install test eval serve build lint fmt

install:
	uv venv && uv pip install -e ".[dev]"

test:
	uv run pytest -q

test-live:
	TNA_RUN_LIVE_TESTS=1 uv run pytest -m live -v

eval:
	uv run python scripts/run_eval.py

eval-refresh-golden:
	uv run python scripts/refresh_golden.py

serve:
	uv run uvicorn tna_service.interface.router:app --host 0.0.0.0 --port 8000

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

lint:
	uv run ruff check src tests evals

fmt:
	uv run ruff format src tests evals
