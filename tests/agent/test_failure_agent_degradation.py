"""Agent failure tests: how agents degrade under various bad LLM responses.

Covers four failure modes:
  1. LLM raises (transport / network failure)
  2. LLM returns data with the wrong type for a field
  3. LLM returns data missing a required field
  4. LLM returns data with unexpected extra fields

In every case the agent should yield a usable default and NOT propagate the
exception — the orchestrator depends on this for graceful degradation.
"""
from __future__ import annotations
from app.services.agents.field_namer import FieldNamer
from app.components.sheet_classifier import SheetClassifier
from app.services.planner.plan import SheetRowPlanner
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
import app.repositories.workbook_tools.survey  # noqa: F401 — register tools
from tests.fixtures.case import fixture_case


class _RaisingLLM:
    """Always raises — simulates HTTP / SDK error."""

    def complete_with_schema(self, system, user, output_schema, tool_name=None,
                             agent_name="unknown", attempt=1):
        raise RuntimeError("simulated LLM transport failure")


class _BadResponseLLM:
    """Returns a literal dict that will be passed into output_schema(**dict).

    If the dict doesn't conform, Pydantic raises ValidationError — the agent
    wrapper is expected to catch that and return the fallback.
    """

    def __init__(self, response: dict):
        self._response = response

    def complete_with_schema(self, system, user, output_schema, tool_name=None,
                             agent_name="unknown", attempt=1):
        return output_schema(**self._response), "{}", 0, 0


# ---------------------------------------------------------------------------
# Failure mode 1: LLM transport exception
# ---------------------------------------------------------------------------


@fixture_case("agent_returns_invalid_json")
def test_field_namer_falls_back_when_llm_raises(fixture):
    """LLM transport failure → empty CanonicalNameMap fallback."""
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    out = FieldNamer(llm=_RaisingLLM()).run(workbook_ctx=fixture.ctx, plan=plan)
    expected = fixture.expectations("agent")["field_namer"]["expected_fallback_name_map"]
    assert out["name_map"].field_labels == expected["field_labels"]
    assert out["name_map"].stage_names == expected["stage_names"]


@fixture_case("agent_returns_invalid_json")
def test_sheet_classifier_falls_back_when_llm_raises(fixture):
    """LLM transport failure → classifier falls back to all sheets."""
    summary = TOOL_REGISTRY.get("workbook_summary")(fixture.ctx)
    out = SheetClassifier(llm=_RaisingLLM()).run(
        workbook_ctx=fixture.ctx, workbook_summary=summary
    )
    # On transport failure the fallback returns all sheet names (false-positive safe).
    assert isinstance(out["relevant_sheets"], list)
    assert out["relevant_sheets"] == list(summary.sheet_names)


# ---------------------------------------------------------------------------
# Failure mode 2: LLM returns wrong type for a field
# ---------------------------------------------------------------------------


@fixture_case("agent_returns_invalid_json")
def test_field_namer_falls_back_on_wrong_type(fixture):
    """LLM returns string instead of dict for field_labels → Pydantic raises → fallback."""
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    # Pass a list of strings — definitely not a dict[str, str]; Pydantic raises.
    bad = _BadResponseLLM({"field_labels": ["IO NO", "extra"], "stage_names": {}})
    out = FieldNamer(llm=bad).run(workbook_ctx=fixture.ctx, plan=plan)
    assert out["name_map"].field_labels == {}
    assert out["name_map"].stage_names == {}


@fixture_case("agent_returns_invalid_json")
def test_sheet_classifier_falls_back_on_wrong_type(fixture):
    """LLM returns string instead of list for relevant_sheets → Pydantic raises → fallback."""
    summary = TOOL_REGISTRY.get("workbook_summary")(fixture.ctx)
    # Pass an integer — not a list[str]; Pydantic raises.
    bad = _BadResponseLLM({"relevant_sheets": 42})
    out = SheetClassifier(llm=bad).run(
        workbook_ctx=fixture.ctx, workbook_summary=summary
    )
    # Fallback: classifier returns all sheets when the agent fails.
    assert isinstance(out["relevant_sheets"], list)
    assert out["relevant_sheets"] == list(summary.sheet_names)


# ---------------------------------------------------------------------------
# Failure mode 3: LLM returns dict missing required fields (Pydantic uses defaults)
# ---------------------------------------------------------------------------


@fixture_case("agent_returns_invalid_json")
def test_field_namer_falls_back_on_missing_required_fields(fixture):
    """LLM returns empty dict — CanonicalNameMap has default_factory so Pydantic accepts it.

    The agent should still produce a valid object with empty maps, not raise.
    """
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    bad = _BadResponseLLM({})
    out = FieldNamer(llm=bad).run(workbook_ctx=fixture.ctx, plan=plan)
    assert out["name_map"].field_labels == {}
    assert out["name_map"].stage_names == {}


# ---------------------------------------------------------------------------
# Failure mode 4: LLM returns dict with extra/unknown fields
# ---------------------------------------------------------------------------


@fixture_case("agent_returns_invalid_json")
def test_field_namer_tolerates_extra_fields(fixture):
    """LLM returns dict with an unknown extra field → Pydantic ignores it.

    CanonicalNameMap uses model_config = ConfigDict(extra='ignore') so extra
    keys silently drop. The agent should still produce the expected fields.
    """
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    bad = _BadResponseLLM({
        "field_labels": {"IO NO": "io_number"},
        "stage_names": {},
        "unknown_extra_field": "should be ignored",
    })
    out = FieldNamer(llm=bad).run(workbook_ctx=fixture.ctx, plan=plan)
    assert out["name_map"].field_labels == {"IO NO": "io_number"}
    assert out["name_map"].stage_names == {}
