.PHONY: install test test-live eval serve build up down logs lint fmt clean

install:
	python -m venv .venv
	. .venv/Scripts/activate && pip install --upgrade pip && pip install -e ".[dev]"

test:
	. .venv/Scripts/activate && pytest -q

test-live:
	. .venv/Scripts/activate && TNA_RUN_LIVE_TESTS=1 pytest -m live -v

eval:
	. .venv/Scripts/activate && python scripts/run_eval.py

eval-refresh-golden:
	. .venv/Scripts/activate && python scripts/refresh_golden.py

serve:
	. .venv/Scripts/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

lint:
	. .venv/Scripts/activate && ruff check app tests evals

fmt:
	. .venv/Scripts/activate && ruff format app tests evals

clean:
	rm -rf .venv .pytest_cache .ruff_cache .coverage htmlcov *.egg-info
