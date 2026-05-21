"""FieldNamer canonical-name allow-list validator tests."""
from __future__ import annotations

from app.agents.field_namer.schema import CanonicalNameMap
from app.agents.field_namer.validators import validate_canonical_name_map


# ---------------------------------------------------------------------------
# happy paths
# ---------------------------------------------------------------------------

def test_all_empty_ok() -> None:
    out = CanonicalNameMap()
    assert validate_canonical_name_map(out, ctx=None).is_ok


def test_field_labels_canonical_and_ignore_ok() -> None:
    out = CanonicalNameMap(field_labels={"IO No": "io_number", "Notes": "ignore"})
    assert validate_canonical_name_map(out, ctx=None).is_ok


def test_field_labels_order_qty_to_quantity_ok() -> None:
    out = CanonicalNameMap(field_labels={"Order Qty": "quantity"})
    assert validate_canonical_name_map(out, ctx=None).is_ok


def test_stage_names_sewing_start_ok() -> None:
    out = CanonicalNameMap(stage_names={"Sewing Start": "sewing_start"})
    assert validate_canonical_name_map(out, ctx=None).is_ok


def test_stage_subfield_labels_plan_to_planned_date_ok() -> None:
    out = CanonicalNameMap(stage_subfield_labels={"Plan": "planned_date"})
    assert validate_canonical_name_map(out, ctx=None).is_ok


def test_confidence_at_boundary_ok() -> None:
    out = CanonicalNameMap(
        field_labels={"Qty": "quantity"},
        field_confidence={"quantity": 0.0},
        stage_confidence={},
    )
    assert validate_canonical_name_map(out, ctx=None).is_ok


def test_confidence_at_one_ok() -> None:
    out = CanonicalNameMap(
        field_confidence={"io_number": 1.0},
        stage_confidence={"ex_factory": 1.0},
    )
    assert validate_canonical_name_map(out, ctx=None).is_ok


# ---------------------------------------------------------------------------
# rejection paths — field_labels
# ---------------------------------------------------------------------------

def test_made_up_canonical_in_field_labels_triggers_retry() -> None:
    out = CanonicalNameMap(field_labels={"Job #": "made_up_canonical"})
    result = validate_canonical_name_map(out, ctx=None)
    assert result.is_retry
    assert "made_up_canonical" in result.reason


# ---------------------------------------------------------------------------
# rejection paths — stage_names
# ---------------------------------------------------------------------------

def test_pli_field_name_used_as_stage_triggers_retry() -> None:
    # ex_factory_date is a PLI metadata canonical, NOT a stage canonical
    out = CanonicalNameMap(stage_names={"Sewing": "ex_factory_date"})
    result = validate_canonical_name_map(out, ctx=None)
    assert result.is_retry
    assert "ex_factory_date" in result.reason


def test_valid_stage_name_ok() -> None:
    out = CanonicalNameMap(stage_names={"Ex Factory Shipment": "ex_factory"})
    assert validate_canonical_name_map(out, ctx=None).is_ok


# ---------------------------------------------------------------------------
# rejection paths — field_confidence out of range
# ---------------------------------------------------------------------------

def test_field_confidence_above_one_triggers_retry() -> None:
    out = CanonicalNameMap(field_confidence={"quantity": 1.5})
    result = validate_canonical_name_map(out, ctx=None)
    assert result.is_retry
    assert "1.5" in result.reason


def test_field_confidence_below_zero_triggers_retry() -> None:
    out = CanonicalNameMap(field_confidence={"io_number": -0.1})
    result = validate_canonical_name_map(out, ctx=None)
    assert result.is_retry
    assert "-0.1" in result.reason


# ---------------------------------------------------------------------------
# rejection paths — stage_confidence out of range
# ---------------------------------------------------------------------------

def test_stage_confidence_above_one_triggers_retry() -> None:
    out = CanonicalNameMap(stage_confidence={"ex_factory": 2.0})
    result = validate_canonical_name_map(out, ctx=None)
    assert result.is_retry


def test_stage_confidence_below_zero_triggers_retry() -> None:
    out = CanonicalNameMap(stage_confidence={"cutting": -0.5})
    result = validate_canonical_name_map(out, ctx=None)
    assert result.is_retry
