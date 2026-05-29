"""CanvasReconciler — assemble ExtractionResult from canvas-arch outputs."""
from __future__ import annotations

import datetime as dt

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding, ValidationWarning
from app.components.workbook.canvas_reconciler import CanvasReconciler
from app.models.extraction import ExtractionResult, PLI
from app.specs.enums import FieldScope
from app.specs.schemas import FinalStage, MetadataEntry


def _f(canonical: str, col: str, row: int, *,
        value: object = "v",
        confidence: Confidence = Confidence.HIGH) -> Finding:
    return Finding(
        canonical=canonical, label_coord=(col, 2),
        value_coord=(col, row), value=value,
        confidence=confidence, evidence=[],
    )


def _stage(**overrides) -> FinalStage:
    base = dict(
        name="Fabric", canonical="fabric",
        plan_date=dt.date(2026, 5, 1), plan_date_col=4,
        column_range=(4, 6), stage_metadata={},
    )
    base.update(overrides)
    return FinalStage(**base)


def _entry(**overrides) -> MetadataEntry:
    base = dict(key="Buyer", value="Nike", source="K4",
                  canonical="buyer", scope=FieldScope.SHEET)
    base.update(overrides)
    return MetadataEntry(**base)


def _run(**overrides) -> ExtractionResult:
    base = dict(
        findings=[], stages_per_row={}, metadata=[], warnings=[],
        source_file="test.xlsx", sheet="S1",
    )
    base.update(overrides)
    return CanvasReconciler().run(**base)["result"]


# ─── Empty / smoke paths ─────────────────────────────────────────────────


def test_empty_inputs_yield_empty_result() -> None:
    result = _run()
    assert result.plis == []
    assert result.warnings == []


def test_warnings_map_to_public_warning_model() -> None:
    w = ValidationWarning(
        name="missing_mandatory_io_number", severity="error",
        message="row 3 missing io_number",
    )
    result = _run(warnings=[w])
    assert len(result.warnings) == 1
    assert result.warnings[0].message == "row 3 missing io_number"
    assert result.warnings[0].severity == "error"
    assert result.warnings[0].check == "missing_mandatory_io_number"


# ─── PLI assembly from findings ──────────────────────────────────────────


def test_findings_group_by_row_into_separate_plis() -> None:
    findings = [
        _f("io_number",  "A", 3, value="IO-1"),
        _f("io_number",  "A", 4, value="IO-2"),
    ]
    result = _run(findings=findings)
    assert len(result.plis) == 2
    assert result.plis[0].io_number == "IO-1"
    assert result.plis[1].io_number == "IO-2"


def test_pli_fields_map_from_canonicals() -> None:
    findings = [
        _f("io_number",     "A", 3, value="IO-1"),
        _f("style_code",    "B", 3, value="STY-1"),
        _f("style_name",    "C", 3, value="Polo Shirt"),
        _f("color_code",    "D", 3, value="NVY"),
        _f("color_name",    "E", 3, value="Navy"),
        _f("fabric_code",   "F", 3, value="CTN"),
        _f("quantity",      "G", 3, value=100),
        _f("delivery_date", "H", 3, value=dt.date(2026, 6, 1)),
    ]
    result = _run(findings=findings)
    pli = result.plis[0]
    assert pli.io_number     == "IO-1"
    assert pli.style_code    == "STY-1"
    assert pli.style_name    == "Polo Shirt"
    assert pli.color_code    == "NVY"
    assert pli.color_name    == "Navy"
    assert pli.fabric_code   == "CTN"
    assert pli.quantity      == 100
    assert pli.delivery_date == dt.date(2026, 6, 1)


def test_per_field_confidence_mapped_to_float() -> None:
    findings = [
        _f("io_number",  "A", 3, value="IO-1",   confidence=Confidence.HIGH),
        _f("style_code", "B", 3, value="STY-1",  confidence=Confidence.MEDIUM),
        _f("quantity",   "C", 3, value=100,      confidence=Confidence.LOW),
    ]
    pli = _run(findings=findings).plis[0]
    assert pli.confidence["io_number"]  == 1.0
    assert pli.confidence["style_code"] == 0.5
    assert pli.confidence["quantity"]   == 0.2


def test_source_cells_populated_from_value_coords() -> None:
    findings = [
        _f("io_number", "A", 3, value="IO-1"),
        _f("style_code", "B", 3, value="STY-1"),
    ]
    pli = _run(findings=findings).plis[0]
    assert pli.source.cells["io_number"]  == "A3"
    assert pli.source.cells["style_code"] == "B3"
    assert pli.source.sheet == "S1"
    assert pli.source.rows == [3]


def test_highest_confidence_finding_wins_for_canonical() -> None:
    """Duplicate findings for the same canonical: highest confidence wins."""
    findings = [
        _f("io_number", "A", 3, value="IO-low",  confidence=Confidence.LOW),
        _f("io_number", "A", 3, value="IO-high", confidence=Confidence.HIGH),
    ]
    pli = _run(findings=findings).plis[0]
    assert pli.io_number == "IO-high"


def test_non_pli_canonicals_excluded_from_pli_fields() -> None:
    """shipment_date / ex_fty_date / fabric_name don't have flat PLI fields."""
    findings = [
        _f("io_number",     "A", 3, value="IO-1"),
        _f("shipment_date", "B", 3, value=dt.date(2026, 5, 15)),
        _f("ex_fty_date",   "C", 3, value=dt.date(2026, 5, 10)),
        _f("fabric_name",   "D", 3, value="Cotton Knit"),
    ]
    pli = _run(findings=findings).plis[0]
    # The non-PLI canonicals are silently absorbed (no flat field for them).
    assert pli.io_number == "IO-1"
    assert "shipment_date" not in pli.confidence
    assert "ex_fty_date" not in pli.confidence
    assert "fabric_name" not in pli.confidence


# ─── Stages ──────────────────────────────────────────────────────────────


def test_stages_attached_per_row() -> None:
    findings = [_f("io_number", "A", 3, value="IO-1")]
    stages = {3: [
        _stage(name="Sample Inspection", canonical=None),    # canonical=None → raw name wins
        _stage(name="Cutting Phase", canonical="cutting"),   # canonical wins over raw name
    ]}
    pli = _run(findings=findings, stages_per_row=stages).plis[0]
    assert len(pli.stages) == 2
    assert pli.stages[0].name == "Sample Inspection"
    assert pli.stages[1].name == "cutting"


def test_stage_planned_date_carried_through() -> None:
    findings = [_f("io_number", "A", 3, value="IO-1")]
    stages = {3: [_stage(plan_date=dt.date(2026, 5, 15))]}
    pli = _run(findings=findings, stages_per_row=stages).plis[0]
    assert pli.stages[0].planned_date == dt.date(2026, 5, 15)


def test_stage_metadata_carried_through() -> None:
    findings = [_f("io_number", "A", 3, value="IO-1")]
    stages = {3: [_stage(stage_metadata={"actual_date": "2026-05-05", "status": "done"})]}
    pli = _run(findings=findings, stages_per_row=stages).plis[0]
    assert pli.stages[0].metadata == {"actual_date": "2026-05-05", "status": "done"}


def test_row_with_only_stages_yields_pli() -> None:
    """A row with no findings but with stages still produces a PLI."""
    stages = {3: [_stage()]}
    result = _run(stages_per_row=stages)
    assert len(result.plis) == 1
    assert result.plis[0].io_number is None
    assert len(result.plis[0].stages) == 1


# ─── Metadata ────────────────────────────────────────────────────────────


def test_sheet_scoped_metadata_lands_on_every_pli() -> None:
    findings = [
        _f("io_number", "A", 3, value="IO-1"),
        _f("io_number", "A", 4, value="IO-2"),
    ]
    metadata = [_entry(key="Buyer", value="Nike", canonical="buyer",
                       scope=FieldScope.SHEET)]
    plis = _run(findings=findings, metadata=metadata).plis
    for pli in plis:
        assert pli.metadata["buyer"] == "Nike"


def test_pli_scoped_metadata_lands_only_on_matching_row() -> None:
    findings = [
        _f("io_number", "A", 3, value="IO-1"),
        _f("io_number", "A", 4, value="IO-2"),
    ]
    metadata = [_entry(key="Treatment", value="Dye",
                       source="K3", canonical=None, scope=FieldScope.PLI)]
    plis = _run(findings=findings, metadata=metadata).plis
    assert plis[0].metadata.get("Treatment") == "Dye"
    assert "Treatment" not in plis[1].metadata


def test_metadata_without_canonical_uses_raw_key() -> None:
    findings = [_f("io_number", "A", 3, value="IO-1")]
    metadata = [_entry(key="Country of Origin", value="VN",
                       canonical=None, scope=FieldScope.SHEET)]
    pli = _run(findings=findings, metadata=metadata).plis[0]
    assert pli.metadata["Country of Origin"] == "VN"


# ─── Ordering ────────────────────────────────────────────────────────────


def test_plis_emitted_in_row_order() -> None:
    findings = [
        _f("io_number", "A", 7, value="IO-c"),
        _f("io_number", "A", 3, value="IO-a"),
        _f("io_number", "A", 5, value="IO-b"),
    ]
    plis = _run(findings=findings).plis
    assert [p.io_number for p in plis] == ["IO-a", "IO-b", "IO-c"]


# ─── Component plumbing ──────────────────────────────────────────────────


def test_reconciler_sockets_registered() -> None:
    comp = CanvasReconciler()
    inputs = comp.__haystack_input__._sockets_dict
    for socket in ("findings", "stages_per_row", "metadata", "warnings",
                    "source_file", "sheet"):
        assert socket in inputs
    assert "result" in comp.__haystack_output__._sockets_dict


def test_reconciler_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("reconciler", CanvasReconciler())
    assert "reconciler" in pipeline.graph.nodes
