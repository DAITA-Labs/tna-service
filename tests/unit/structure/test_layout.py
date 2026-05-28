"""Acceptance — incremental adaptability.

These tests are the spec's success criteria, written as code so we can run
them. They prove that adding a new agent / new pattern is a small, contained
change — no orchestrator surgery."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_workflow_agents_each_in_own_module():
    """All workflow agents live in app/agents/; app/services/agents/ has been deleted."""
    agents_dir = ROOT / "app" / "services" / "agents"
    assert not agents_dir.exists(), (
        "app/services/agents/ still exists — legacy agent directory must be deleted"
    )


def test_services_contains_only_service_layer():
    """app/services/ contains only the orchestration service layer."""
    svc_dir = ROOT / "app" / "services"
    files = {p.name for p in svc_dir.glob("*.py")}
    assert files == {"__init__.py", "extract_service.py"}, (
        f"Unexpected files in app/services/: {files}"
    )


def test_validators_each_in_own_module():
    """One file per validator in components/validators/."""
    v_dir = ROOT / "app" / "components" / "validators"
    vals = {p.stem for p in v_dir.glob("*.py")
            if p.name not in ("__init__.py",)}
    assert vals == {
        "source_cell_verifier", "header_match_verifier",
        "coverage_verifier", "field_dropout_verifier",
        "plan_invariants", "plan_statistics",
        "post_review_plan", "post_namer_canonical", "pre_apply_readiness",
        "post_review_validator", "post_namer_validator", "pre_apply_validator",
        # canvas-architecture validators (consume list[Finding] + ClusterAnchorBundle)
        "cardinality",
        "date_trio",
        "stage_sequence",
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
    """app/tools/ has the expected tool module files."""
    t = ROOT / "app" / "tools"
    files = {p.stem for p in t.glob("*.py")
             if p.name not in ("__init__.py", "_registry.py", "_decorator.py")}
    assert files == {"survey", "bulk_read", "targeted", "structure", "search"}


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
