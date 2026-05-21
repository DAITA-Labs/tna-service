"""Acceptance — incremental adaptability.

These tests are the spec's success criteria, written as code so we can run
them. They prove that adding a new agent / new pattern is a small, contained
change — no orchestrator surgery."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_workflow_agents_each_in_own_module():
    """One file per workflow agent in services/agents/ (migrated agents move to app/agents/)."""
    agents_dir = ROOT / "app" / "services" / "agents"
    agents = {p.stem for p in agents_dir.glob("*.py")
              if p.name not in ("__init__.py", "_base.py")}
    assert agents == {
        "field_namer",
    }


def test_validators_each_in_own_module():
    """One file per validator in services/validation/."""
    v_dir = ROOT / "app" / "services" / "validation"
    vals = {p.stem for p in v_dir.glob("*.py")
            if p.name not in ("__init__.py",)}
    assert vals == {
        "source_cell_verifier", "header_match_verifier",
        "coverage_verifier", "field_dropout_verifier",
        "plan_invariants", "plan_statistics",
    }


def test_eval_independent_of_app_services():
    """evals/ must not import from app.services.* or app.routers.*
    (scripts/ is where they're wired)."""
    eval_files = list((ROOT / "evals").rglob("*.py"))
    for ef in eval_files:
        text = ef.read_text(encoding="utf-8")
        assert "app.services" not in text, f"{ef} imports app.services"
        assert "app.routers" not in text, f"{ef} imports app.routers"


def test_tools_grouped_by_purpose():
    """workbook_tools/ has the expected 6 module files."""
    t = ROOT / "app" / "repositories" / "workbook_tools"
    files = {p.stem for p in t.glob("*.py")
             if p.name != "__init__.py"}
    assert files == {"_registry", "survey", "bulk_read",
                    "targeted", "structure", "search"}


def test_enums_each_in_own_module():
    """app/enums/ has every Literal/Enum as its own file."""
    enums_dir = ROOT / "app" / "enums"
    enums = {p.stem for p in enums_dir.glob("*.py")
             if p.name != "__init__.py"}
    assert enums >= {
        "environment", "cell_dtype", "location_pattern",
        "validation_severity", "pli_mode", "row_role", "stage_scope",
    }


def test_layered_directories_exist():
    """The microservice layered structure is in place: routers, services,
    repositories, models, enums, schemas, core, config."""
    app = ROOT / "app"
    for sub in ("routers", "services", "repositories", "models", "enums",
                "schemas", "core", "config", "prompts"):
        assert (app / sub).is_dir(), f"missing layer: app/{sub}"
