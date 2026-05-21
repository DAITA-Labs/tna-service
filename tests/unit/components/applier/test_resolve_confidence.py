"""apply_plan._resolve_confidence — picks per-field confidence with calibrated defaults."""
from app.models.artifacts import CanonicalNameMap
from app.components.per_sheet.applier import _resolve_confidence


def test_llm_supplied_confidence_wins() -> None:
    nm = CanonicalNameMap(field_confidence={"io_number": 0.99})
    assert _resolve_confidence(source="header_label", name_map=nm,
                                raw="IO NO", canonical="io_number") == 0.99


def test_kv_anchor_default() -> None:
    nm = CanonicalNameMap()
    assert _resolve_confidence(source="kv_anchor", name_map=nm,
                                raw="IO", canonical="io_number") == 0.95


def test_header_label_default() -> None:
    nm = CanonicalNameMap()
    assert _resolve_confidence(source="header_label", name_map=nm,
                                raw="IO NO", canonical="io_number") == 0.85


def test_stage_column_default() -> None:
    nm = CanonicalNameMap()
    assert _resolve_confidence(source="stage_column", name_map=nm,
                                raw="CUTTING", canonical="cutting") == 0.85


def test_stage_subfield_default() -> None:
    nm = CanonicalNameMap()
    assert _resolve_confidence(source="stage_subfield", name_map=nm,
                                raw="Actual", canonical="actual_date") == 0.80


def test_metadata_fallback_default() -> None:
    nm = CanonicalNameMap()
    assert _resolve_confidence(source="metadata_fallback", name_map=nm,
                                raw="Unknown", canonical="Unknown") == 0.40


def test_unknown_source_default() -> None:
    nm = CanonicalNameMap()
    assert _resolve_confidence(source="other", name_map=nm, raw="x", canonical="x") == 0.5
