"""MergeAlignmentValidator — sibling identifier columns respect io_number merges."""
from __future__ import annotations

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding
from app.artifacts.structure import MergeSpan, Rect
from app.components.validators.merge_alignment import MergeAlignmentValidator
from tests.unit.components.field._bundles import make_bundle


def _bundle(merge_spans: list[MergeSpan] | None = None, n_rows: int = 12, n_cols: int = 8):
    values = [[None] * n_cols for _ in range(n_rows)]
    return make_bundle(values, "io_number", columns={}, rows={}, merge_spans=merge_spans)


def _f(canonical: str, col: str, row: int, value: object = "v") -> Finding:
    return Finding(
        canonical=canonical, label_coord=(col, 2),
        value_coord=(col, row), value=value,
        confidence=Confidence.HIGH, evidence=[],
    )


def _vmerge(col: int, r0: int, r1: int) -> MergeSpan:
    """Vertical MergeSpan at a single 1-indexed column from row r0 to r1."""
    return MergeSpan(rect=Rect(r0=r0, c0=col, r1=r1, c1=col), orientation="vertical")


# ─── No-trigger paths ─────────────────────────────────────────────────────


def test_no_io_findings_no_warnings() -> None:
    """Validator can't locate io_number column → no checks possible."""
    findings = [_f("style_code", "B", 4), _f("style_code", "B", 5)]
    assert MergeAlignmentValidator().run(
        findings=findings,
        bundle=_bundle(merge_spans=[_vmerge(1, 4, 6)]),
    )["warnings"] == []


def test_no_vertical_merges_no_warnings() -> None:
    """Without io_number merges, no row-group partition is enforced."""
    findings = [
        _f("io_number",  "A", 4),
        _f("style_code", "B", 4),
        _f("style_code", "B", 5),
    ]
    assert MergeAlignmentValidator().run(
        findings=findings, bundle=_bundle(merge_spans=[]),
    )["warnings"] == []


def test_horizontal_merge_at_io_column_ignored() -> None:
    """Only vertical merges at the io_number column define a row-group."""
    findings = [
        _f("io_number",  "A", 4),
        _f("style_code", "B", 4),
        _f("style_code", "B", 5),
    ]
    bundle = _bundle(merge_spans=[
        MergeSpan(rect=Rect(4, 1, 4, 6), orientation="horizontal"),   # horizontal
    ])
    assert MergeAlignmentValidator().run(findings=findings, bundle=bundle)["warnings"] == []


def test_merge_at_non_io_column_ignored() -> None:
    """A vertical merge at column other than io_number doesn't enforce anything."""
    findings = [
        _f("io_number",  "A", 4),
        _f("style_code", "B", 4),
        _f("style_code", "B", 5),
    ]
    bundle = _bundle(merge_spans=[_vmerge(3, 4, 6)])   # merge at col C, not io's col A
    assert MergeAlignmentValidator().run(findings=findings, bundle=bundle)["warnings"] == []


# ─── Single-finding-in-merge happy paths ──────────────────────────────────


def test_sibling_with_one_finding_in_merge_no_warning() -> None:
    """The expected pattern: io_number merged 4-6, style_code anchors row 4 only."""
    findings = [
        _f("io_number",  "A", 4),
        _f("style_code", "B", 4),
    ]
    bundle = _bundle(merge_spans=[_vmerge(1, 4, 6)])
    assert MergeAlignmentValidator().run(findings=findings, bundle=bundle)["warnings"] == []


def test_sibling_with_no_findings_in_merge_no_warning() -> None:
    """Sibling column may have no finding at all inside the merge — that's fine."""
    findings = [
        _f("io_number",  "A", 4),
        _f("color_code", "C", 8),     # outside the 4-6 merge range
    ]
    bundle = _bundle(merge_spans=[_vmerge(1, 4, 6)])
    assert MergeAlignmentValidator().run(findings=findings, bundle=bundle)["warnings"] == []


# ─── Violations ───────────────────────────────────────────────────────────


def test_sibling_with_multiple_findings_in_merge_emits_warning() -> None:
    """The trigger: io_number merged 4-6 but style_code at 4, 5, 6 = 3 distinct PLIs."""
    findings = [
        _f("io_number",  "A", 4),
        _f("style_code", "B", 4, value="S1"),
        _f("style_code", "B", 5, value="S2"),
        _f("style_code", "B", 6, value="S3"),
    ]
    bundle = _bundle(merge_spans=[_vmerge(1, 4, 6)])
    out = MergeAlignmentValidator().run(findings=findings, bundle=bundle)
    assert len(out["warnings"]) == 1
    w = out["warnings"][0]
    assert w.name == "merge_alignment_violation"
    assert w.severity == "warning"
    assert "io_number" in w.message
    assert "style_code" in w.message
    assert "[4, 5, 6]" in w.message
    assert "rows 4-6" in w.message
    assert len(w.affects_findings) == 3


def test_violation_carries_only_offending_findings_in_affects() -> None:
    findings = [
        _f("io_number",  "A", 4),
        _f("style_code", "B", 4, value="S1"),
        _f("style_code", "B", 5, value="S2"),
        _f("style_code", "B", 9, value="S3"),    # outside merge — must NOT be in affects
    ]
    bundle = _bundle(merge_spans=[_vmerge(1, 4, 6)])
    out = MergeAlignmentValidator().run(findings=findings, bundle=bundle)
    rows = sorted(f.value_coord[1] for f in out["warnings"][0].affects_findings)
    assert rows == [4, 5]


def test_two_violating_canonicals_emit_separate_warnings() -> None:
    findings = [
        _f("io_number",  "A", 4),
        _f("color_code", "B", 4), _f("color_code", "B", 5),
        _f("style_code", "C", 4), _f("style_code", "C", 5),
    ]
    bundle = _bundle(merge_spans=[_vmerge(1, 4, 6)])
    out = MergeAlignmentValidator().run(findings=findings, bundle=bundle)
    assert len(out["warnings"]) == 2
    canonicals = sorted({w.affects_findings[0].canonical for w in out["warnings"]})
    assert canonicals == ["color_code", "style_code"]


def test_multiple_io_merges_each_evaluated() -> None:
    findings = [
        _f("io_number",  "A", 4), _f("io_number",  "A", 8),
        _f("style_code", "B", 4), _f("style_code", "B", 5),    # violates merge 4-6
        _f("style_code", "B", 8),                                # ok inside merge 8-10
    ]
    bundle = _bundle(merge_spans=[_vmerge(1, 4, 6), _vmerge(1, 8, 10)])
    out = MergeAlignmentValidator().run(findings=findings, bundle=bundle)
    assert len(out["warnings"]) == 1
    assert "rows 4-6" in out["warnings"][0].message


def test_violation_at_merge_boundary_inclusive() -> None:
    """Findings on both r0 and r1 of the merge count as within range."""
    findings = [
        _f("io_number",  "A", 4),
        _f("style_code", "B", 4), _f("style_code", "B", 6),    # exactly at boundaries
    ]
    bundle = _bundle(merge_spans=[_vmerge(1, 4, 6)])
    assert MergeAlignmentValidator().run(findings=findings, bundle=bundle)["warnings"]


# ─── io_number-itself behaviour ───────────────────────────────────────────


def test_io_number_excluded_from_sibling_count() -> None:
    """Even if io_number has multiple findings inside its own merge, we don't self-warn."""
    findings = [
        _f("io_number", "A", 4), _f("io_number", "A", 5), _f("io_number", "A", 6),
    ]
    bundle = _bundle(merge_spans=[_vmerge(1, 4, 6)])
    out = MergeAlignmentValidator().run(findings=findings, bundle=bundle)
    assert [w for w in out["warnings"] if "io_number" in w.affects_findings[0].canonical] == []


# ─── Component plumbing ──────────────────────────────────────────────────


def test_validator_sockets_registered() -> None:
    comp = MergeAlignmentValidator()
    assert "findings" in comp.__haystack_input__._sockets_dict
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "warnings" in comp.__haystack_output__._sockets_dict


def test_validator_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("merge_align", MergeAlignmentValidator())
    assert "merge_align" in pipeline.graph.nodes
