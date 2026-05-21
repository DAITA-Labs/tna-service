"""Sub-plan 5 phase D — between-agents validator tests."""
from __future__ import annotations

from app.components.validators.post_namer_canonical import validate_post_namer
from app.components.validators.post_review_plan import validate_post_review
from app.components.validators.pre_apply_readiness import validate_pre_apply
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import (
    CanonicalNameMap, HeaderLabel, KVAnchor, PliBlock, RowSpec,
    SheetPlan, StageBandSpec, StageColumn, ValidationFinding,
)


def _row_per_pli_plan() -> SheetPlan:
    return SheetPlan(
        sheet="S1",
        pli_mode=PliMode.ROW_PER_PLI,
        stage_scope=StageScope.SHEET_LEVEL,
        header_rows=[1],
        header_labels=[HeaderLabel(raw="IO No", col="A", row=1, confidence=1.0)],
        rows=[RowSpec(idx=1, role=RowRole.HEADER), RowSpec(idx=2, role=RowRole.ANCHOR)],
        pli_blocks=[],
        kv_anchors=[],
        stage_bands=[],
        confidence=0.9,
    )


# === post_review_plan ===

def test_post_review_clean_plan_returns_no_findings() -> None:
    plan = _row_per_pli_plan()
    assert validate_post_review(plan) == []


def test_post_review_propagates_both_errors_and_warnings() -> None:
    """Both severities propagate so warnings introduced by PlanReviewer aren't lost."""
    from unittest.mock import patch

    # Inject a fake invariants result: one ERROR + one WARN
    fake = [
        ValidationFinding(
            check="row_uniqueness",
            severity=ValidationSeverity.ERROR,
            message="row 7 duplicated",
        ),
        ValidationFinding(
            check="vocabulary_overlap",
            severity=ValidationSeverity.WARN,
            message="header vocab thin",
        ),
    ]
    with patch(
        "app.components.validators.post_review_plan.validate_invariants",
        return_value=fake,
    ):
        out = validate_post_review(_row_per_pli_plan())
    assert {f.severity for f in out} == {ValidationSeverity.ERROR, ValidationSeverity.WARN}
    assert all(f.check.startswith("post_review_plan/") for f in out)


# === post_namer_canonical ===

def test_post_namer_returns_finding_for_dropped_label() -> None:
    plan = _row_per_pli_plan()
    name_map = CanonicalNameMap()  # empty — "IO No" was detected but not mapped
    findings = validate_post_namer(plan, name_map)
    assert len(findings) == 1
    assert "IO No" in findings[0].message


def test_post_namer_accepts_ignore_mapping() -> None:
    plan = _row_per_pli_plan()
    name_map = CanonicalNameMap(field_labels={"IO No": "ignore"})
    assert validate_post_namer(plan, name_map) == []


def test_post_namer_accepts_canonical_mapping() -> None:
    plan = _row_per_pli_plan()
    name_map = CanonicalNameMap(field_labels={"IO No": "io_number"})
    assert validate_post_namer(plan, name_map) == []


# === pre_apply_readiness ===

def test_pre_apply_row_per_pli_with_header_labels_passes() -> None:
    plan = _row_per_pli_plan()
    assert validate_pre_apply(plan) == []


def test_pre_apply_row_per_pli_without_header_labels_fails() -> None:
    plan = _row_per_pli_plan().model_copy(update={"header_labels": []})
    findings = validate_pre_apply(plan)
    assert len(findings) == 1
    assert findings[0].severity is ValidationSeverity.ERROR


def test_pre_apply_sheet_is_pli_without_kv_anchors_fails() -> None:
    plan = SheetPlan(
        sheet="S2",
        pli_mode=PliMode.SHEET_IS_PLI,
        stage_scope=StageScope.PLI_LOCAL,
        header_rows=[],
        rows=[],
        pli_blocks=[],
        kv_anchors=[],
        stage_bands=[],
        confidence=0.9,
    )
    findings = validate_pre_apply(plan)
    assert any("kv_anchors" in f.message for f in findings)


def test_pre_apply_section_per_pli_without_blocks_fails() -> None:
    plan = SheetPlan(
        sheet="S3",
        pli_mode=PliMode.SECTION_PER_PLI,
        stage_scope=StageScope.SECTION_LOCAL,
        header_rows=[],
        rows=[],
        pli_blocks=[],
        kv_anchors=[],
        stage_bands=[],
        confidence=0.9,
    )
    findings = validate_pre_apply(plan)
    assert any("pli_blocks" in f.message for f in findings)


def test_pre_apply_section_per_pli_block_without_identity_fails() -> None:
    plan = SheetPlan(
        sheet="S4",
        pli_mode=PliMode.SECTION_PER_PLI,
        stage_scope=StageScope.SECTION_LOCAL,
        header_rows=[],
        rows=[],
        pli_blocks=[PliBlock(id=0, bbox=(1, 10), identity=[])],
        kv_anchors=[],
        stage_bands=[],
        confidence=0.9,
    )
    findings = validate_pre_apply(plan)
    assert any("identity is empty" in f.message for f in findings)
