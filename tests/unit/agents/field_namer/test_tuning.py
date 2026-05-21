"""FieldNamerTuning unit tests — defaults and canonical list membership."""
from __future__ import annotations

from app.agents.field_namer.tuning import FieldNamerTuning
from app.inferencing.tuning import AgentTuning


def test_field_namer_tuning_inherits_agent_tuning() -> None:
    assert issubclass(FieldNamerTuning, AgentTuning)


def test_defaults_max_retries() -> None:
    t = FieldNamerTuning()
    assert t.max_retries == 1


def test_defaults_capture_decision_notes() -> None:
    t = FieldNamerTuning()
    assert t.capture_decision_notes is False


def test_pli_field_canonicals_contains_io_number() -> None:
    t = FieldNamerTuning()
    assert "io_number" in t.pli_field_canonicals


def test_pli_field_canonicals_contains_quantity() -> None:
    t = FieldNamerTuning()
    assert "quantity" in t.pli_field_canonicals


def test_stage_canonicals_contains_ex_factory() -> None:
    t = FieldNamerTuning()
    assert "ex_factory" in t.stage_canonicals


def test_stage_canonicals_contains_sewing_start() -> None:
    t = FieldNamerTuning()
    assert "sewing_start" in t.stage_canonicals


def test_subfield_canonicals_contains_planned_date() -> None:
    t = FieldNamerTuning()
    assert "planned_date" in t.subfield_canonicals


def test_metadata_bound_canonicals_contains_ex_factory_date() -> None:
    t = FieldNamerTuning()
    assert "ex_factory_date" in t.metadata_bound_canonicals


def test_canonical_lists_are_independent_copies() -> None:
    t1 = FieldNamerTuning()
    t2 = FieldNamerTuning()
    t1.pli_field_canonicals.append("custom")
    assert "custom" not in t2.pli_field_canonicals
