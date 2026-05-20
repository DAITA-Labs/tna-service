.PHONY: install test test-live eval eval-smoke serve build up down logs lint fmt clean

# Activate-script path differs by platform (Windows: Scripts/, POSIX: bin/).
ifeq ($(OS),Windows_NT)
VENV_ACTIVATE := . .venv/Scripts/activate
else
VENV_ACTIVATE := . .venv/bin/activate
endif

install:
	python -m venv .venv
	$(VENV_ACTIVATE) && pip install --upgrade pip && pip install -e ".[dev]"

test:
	$(VENV_ACTIVATE) && pytest -q

test-live:
	$(VENV_ACTIVATE) && TNA_RUN_LIVE_TESTS=1 pytest -m live -v

eval:
	$(VENV_ACTIVATE) && python scripts/run_eval.py

eval-smoke:
	$(VENV_ACTIVATE) && python scripts/run_eval.py --smoke

eval-refresh-golden:
	$(VENV_ACTIVATE) && python scripts/refresh_golden.py

serve:
	$(VENV_ACTIVATE) && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

lint:
	$(VENV_ACTIVATE) && ruff check app tests evals

fmt:
	$(VENV_ACTIVATE) && ruff format app tests evals

clean:
	rm -rf .venv .pytest_cache .ruff_cache .coverage htmlcov *.egg-info
