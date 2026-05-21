"""FieldNamerInputs and CanonicalNameMap schema tests."""
from __future__ import annotations

from app.agents.field_namer.schema import CanonicalNameMap, FieldNamerInputs
from app.artifacts.agent_io import AgentOutput
from app.enums.pli_mode import PliMode
from app.models.artifacts import SheetPlan


def _minimal_plan() -> SheetPlan:
    return SheetPlan(sheet="Sheet1", pli_mode=PliMode.ROW_PER_PLI)


def test_canonical_name_map_inherits_agent_output() -> None:
    assert issubclass(CanonicalNameMap, AgentOutput)


def test_canonical_name_map_defaults() -> None:
    out = CanonicalNameMap()
    assert out.field_labels == {}
    assert out.stage_names == {}
    assert out.stage_subfield_labels == {}
    assert out.field_confidence == {}
    assert out.stage_confidence == {}
    assert out.decision_notes is None


def test_canonical_name_map_round_trip() -> None:
    out = CanonicalNameMap(
        field_labels={"Job #": "io_number", "Qty": "quantity"},
        stage_names={"Sewing Start": "sewing_start"},
        stage_subfield_labels={"Plan": "planned_date"},
        field_confidence={"io_number": 0.9, "quantity": 1.0},
        stage_confidence={"sewing_start": 0.85},
    )
    dumped = out.model_dump()
    restored = CanonicalNameMap(**dumped)
    assert restored.field_labels["Job #"] == "io_number"
    assert restored.field_labels["Qty"] == "quantity"
    assert restored.stage_names["Sewing Start"] == "sewing_start"
    assert restored.stage_subfield_labels["Plan"] == "planned_date"
    assert restored.field_confidence["io_number"] == 0.9
    assert restored.stage_confidence["sewing_start"] == 0.85


def test_inputs_wraps_plan() -> None:
    plan = _minimal_plan()
    inputs = FieldNamerInputs(plan=plan)
    assert inputs.plan is plan
