"""IdentifierFindingGate — routes ambiguous identifier findings to the judge."""
from __future__ import annotations

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding, ValidationWarning
from app.components.judges._render import render_sheet_excerpt
from app.components.judges.identifier_finding_gate import (
    IdentifierFindingGate,
    _apply_verdict,
    _render_spec_snippet,
)
from app.agents.judges.identifier_finding.schema import (
    IdentifierFindingAudit,
    IdentifierVerdict,
)
from tests.fixtures.fake_llm import FakeLLM
from tests.unit.components.field._bundles import make_bundle


# ─── Fixtures ────────────────────────────────────────────────────────────


def _grid(n_rows: int = 8, n_cols: int = 5,
          overlay: dict[tuple[int, int], object] | None = None) -> list[list[object]]:
    values = [[None] * n_cols for _ in range(n_rows)]
    for (r, c), v in (overlay or {}).items():
        values[r - 1][c - 1] = v
    return values


def _bundle(overlay: dict[tuple[int, int], object] | None = None):
    return make_bundle(_grid(overlay=overlay), "io_number", columns={}, rows={})


def _f(canonical: str, col: str, row: int, *,
        value: object = "IO-1",
        confidence: Confidence = Confidence.HIGH) -> Finding:
    return Finding(
        canonical=canonical, label_coord=(col, 2),
        value_coord=(col, row), value=value,
        confidence=confidence, evidence=["TABULAR_HEADER_MATCH"],
    )


def _keep_verdict() -> dict:
    return {"decision": "keep", "alternative_coord": None,
            "reason": "value matches spec", "confidence": "high"}


def _drop_verdict() -> dict:
    return {"decision": "drop", "alternative_coord": None,
            "reason": "value contradicts anti-pattern", "confidence": "medium"}


def _rewrite_verdict(coord=("B", 3)) -> dict:
    return {"decision": "rewrite", "alternative_coord": list(coord),
            "reason": "column B header is the real io_number column",
            "confidence": "high"}


# ─── Short-circuit paths ──────────────────────────────────────────────────


def test_no_findings_returns_empty() -> None:
    gate = IdentifierFindingGate(llm=FakeLLM(canned={}))
    out = gate.run(findings=[], warnings=[], bundle=_bundle())
    assert out["findings"] == []


def test_all_high_confidence_no_warnings_no_judge_call() -> None:
    """If nothing is ambiguous, the judge is never invoked."""
    gate = IdentifierFindingGate(llm=FakeLLM(canned={}))
    findings = [_f("io_number", "A", 3, confidence=Confidence.HIGH)]
    out = gate.run(findings=findings, warnings=[], bundle=_bundle())
    assert out["findings"] == findings


def test_non_identifier_canonical_with_low_confidence_passes_through() -> None:
    """The gate's prompt is identifier-specific; non-identifier canonicals skip the judge."""
    gate = IdentifierFindingGate(llm=FakeLLM(canned={}))
    findings = [_f("planned_date", "C", 3, confidence=Confidence.LOW)]
    out = gate.run(findings=findings, warnings=[], bundle=_bundle())
    assert out["findings"] == findings


# ─── Trigger: low confidence ──────────────────────────────────────────────


def test_low_confidence_finding_routed_through_keep_path() -> None:
    """LOW confidence → judge invoked → keep verdict → finding preserved."""
    llm = FakeLLM(canned={"IdentifierVerdict": _keep_verdict()})
    gate = IdentifierFindingGate(llm=llm)
    findings = [_f("io_number", "A", 3, confidence=Confidence.LOW)]
    out = gate.run(findings=findings, warnings=[], bundle=_bundle())
    assert len(out["findings"]) == 1
    assert out["findings"][0].canonical == "io_number"
    assert out["findings"][0].value_coord == ("A", 3)


def test_low_confidence_finding_dropped_by_judge() -> None:
    llm = FakeLLM(canned={"IdentifierVerdict": _drop_verdict()})
    gate = IdentifierFindingGate(llm=llm)
    findings = [_f("io_number", "A", 3, confidence=Confidence.LOW)]
    out = gate.run(findings=findings, warnings=[], bundle=_bundle())
    assert out["findings"] == []


def test_low_confidence_finding_rewritten_by_judge() -> None:
    """rewrite → new finding at alternative_coord with the cell's value, evidence tag added."""
    overlay = {(3, 2): "IO-9012"}    # B3
    bundle = _bundle(overlay=overlay)
    llm = FakeLLM(canned={"IdentifierVerdict": _rewrite_verdict(coord=("B", 3))})
    gate = IdentifierFindingGate(llm=llm)
    findings = [_f("io_number", "A", 3, value="STY-7821", confidence=Confidence.LOW)]
    out = gate.run(findings=findings, warnings=[], bundle=bundle)
    assert len(out["findings"]) == 1
    rewritten = out["findings"][0]
    assert rewritten.canonical == "io_number"
    assert rewritten.value_coord == ("B", 3)
    assert rewritten.value == "IO-9012"
    assert "judge_rewrite" in rewritten.evidence
    assert rewritten.confidence is Confidence.HIGH


# ─── Trigger: warning affects finding ─────────────────────────────────────


def test_high_confidence_with_warning_still_routed_to_judge() -> None:
    """An anti_pattern_match warning fires the judge even though confidence is HIGH."""
    finding = _f("io_number", "A", 3, confidence=Confidence.HIGH)
    warning = ValidationWarning(
        name="anti_pattern_match", severity="warning",
        message="header is STYLE NO", affects_findings=[finding],
    )
    llm = FakeLLM(canned={"IdentifierVerdict": _drop_verdict()})
    gate = IdentifierFindingGate(llm=llm)
    out = gate.run(findings=[finding], warnings=[warning], bundle=_bundle())
    assert out["findings"] == []


# ─── Fail-safe: judge run failure → keep ─────────────────────────────────


def test_judge_failure_keeps_finding() -> None:
    """Both LLM responses fail validation → AgentRunFailure → gate keeps the finding."""
    bad = {"decision": "rewrite", "alternative_coord": None,
            "reason": "x", "confidence": "low"}
    llm = FakeLLM(canned={}).script_responses(bad, bad)
    gate = IdentifierFindingGate(llm=llm)
    finding = _f("io_number", "A", 3, confidence=Confidence.LOW)
    out = gate.run(findings=[finding], warnings=[], bundle=_bundle())
    assert out["findings"] == [finding]


# ─── Order preservation ──────────────────────────────────────────────────


def test_order_preserved_when_judge_keeps_all() -> None:
    """Indexed iteration → original order survives the gate."""
    llm = FakeLLM(canned={"IdentifierVerdict": _keep_verdict()})
    gate = IdentifierFindingGate(llm=llm)
    findings = [
        _f("style_code", "A", 3, confidence=Confidence.HIGH),
        _f("io_number",  "B", 3, confidence=Confidence.LOW),
        _f("color_code", "C", 3, confidence=Confidence.HIGH),
    ]
    out = gate.run(findings=findings, warnings=[], bundle=_bundle())
    canonicals = [f.canonical for f in out["findings"]]
    assert canonicals == ["style_code", "io_number", "color_code"]


def test_drop_removes_finding_but_keeps_neighbours() -> None:
    llm = FakeLLM(canned={"IdentifierVerdict": _drop_verdict()})
    gate = IdentifierFindingGate(llm=llm)
    findings = [
        _f("style_code", "A", 3, confidence=Confidence.HIGH),
        _f("io_number",  "B", 3, confidence=Confidence.LOW),
        _f("color_code", "C", 3, confidence=Confidence.HIGH),
    ]
    out = gate.run(findings=findings, warnings=[], bundle=_bundle())
    canonicals = [f.canonical for f in out["findings"]]
    assert canonicals == ["style_code", "color_code"]


# ─── _apply_verdict helper ───────────────────────────────────────────────


def test_apply_verdict_keep_returns_original() -> None:
    f = _f("io_number", "A", 3)
    v = IdentifierVerdict(decision="keep", reason="x", confidence="high")
    assert _apply_verdict(f, v, _bundle().canvas) is f


def test_apply_verdict_drop_returns_none() -> None:
    f = _f("io_number", "A", 3)
    v = IdentifierVerdict(decision="drop", reason="x", confidence="medium")
    assert _apply_verdict(f, v, _bundle().canvas) is None


def test_apply_verdict_rewrite_reads_cell_value() -> None:
    overlay = {(3, 2): "IO-9012"}
    canvas = _bundle(overlay=overlay).canvas
    f = _f("io_number", "A", 3, value="STY-7821")
    v = IdentifierVerdict(decision="rewrite", alternative_coord=("B", 3),
                           reason="x", confidence="high")
    new = _apply_verdict(f, v, canvas)
    assert new is not None and new.value == "IO-9012"
    assert new.value_coord == ("B", 3)
    assert "judge_rewrite" in new.evidence


def test_apply_verdict_rewrite_maps_judge_confidence() -> None:
    canvas = _bundle().canvas
    f = _f("io_number", "A", 3)
    v_med = IdentifierVerdict(decision="rewrite", alternative_coord=("B", 3),
                                reason="x", confidence="medium")
    new = _apply_verdict(f, v_med, canvas)
    assert new is not None and new.confidence is Confidence.MEDIUM


def test_apply_verdict_rewrite_out_of_bounds_yields_none_value() -> None:
    """If alternative_coord points past the canvas, value comes back as None."""
    canvas = _bundle().canvas
    f = _f("io_number", "A", 3)
    v = IdentifierVerdict(decision="rewrite", alternative_coord=("Z", 99),
                           reason="x", confidence="low")
    new = _apply_verdict(f, v, canvas)
    assert new is not None and new.value is None


# ─── render_sheet_excerpt helper ────────────────────────────────────────


def testrender_sheet_excerpt_includes_centre_and_neighbours() -> None:
    overlay = {(3, 1): "row3-A", (3, 2): "row3-B", (2, 1): "row2-A"}
    canvas = _bundle(overlay=overlay).canvas
    text = render_sheet_excerpt(canvas, ("A", 3), half_rows=1, half_cols=1)
    assert "row3-A" in text
    assert "row3-B" in text
    assert "row2-A" in text


def testrender_sheet_excerpt_clamps_to_canvas_bounds() -> None:
    """Asking for a window past the canvas edge clips without error."""
    canvas = _bundle().canvas
    text = render_sheet_excerpt(canvas, ("A", 1), half_rows=5, half_cols=5)
    assert text  # didn't raise


# ─── _render_spec_snippet helper ─────────────────────────────────────────


def test_render_spec_snippet_known_canonical() -> None:
    text = _render_spec_snippet("io_number")
    assert "io_number" in text
    assert "Patterns" in text or "Anti-patterns" in text or "Examples" in text


def test_render_spec_snippet_unknown_canonical_returns_placeholder() -> None:
    text = _render_spec_snippet("not_a_real_canonical")
    assert "not_a_real_canonical" in text


# ─── Audit output socket ─────────────────────────────────────────────────


def test_audits_empty_when_no_findings() -> None:
    gate = IdentifierFindingGate(llm=FakeLLM(canned={}))
    out = gate.run(findings=[], warnings=[], bundle=_bundle())
    assert out["audits"] == []


def test_audits_empty_when_nothing_ambiguous() -> None:
    """No judge calls → no audit rows."""
    gate = IdentifierFindingGate(llm=FakeLLM(canned={}))
    findings = [_f("io_number", "A", 3, confidence=Confidence.HIGH)]
    out = gate.run(findings=findings, warnings=[], bundle=_bundle())
    assert out["audits"] == []


def test_audit_carries_verdict_for_judged_finding() -> None:
    llm = FakeLLM(canned={"IdentifierVerdict": _keep_verdict()})
    gate = IdentifierFindingGate(llm=llm)
    findings = [_f("io_number", "A", 3, confidence=Confidence.LOW)]
    out = gate.run(findings=findings, warnings=[], bundle=_bundle())
    assert len(out["audits"]) == 1
    audit = out["audits"][0]
    assert isinstance(audit, IdentifierFindingAudit)
    assert audit.finding_index == 0
    assert audit.verdict is not None
    assert audit.verdict.decision == "keep"
    assert audit.judge_failed is False


def test_audit_marks_judge_failed_on_agent_run_failure() -> None:
    """AgentRunFailure path → audit row has verdict=None and judge_failed=True."""
    bad = {"decision": "rewrite", "alternative_coord": None,
            "reason": "x", "confidence": "low"}
    llm = FakeLLM(canned={}).script_responses(bad, bad)
    gate = IdentifierFindingGate(llm=llm)
    findings = [_f("io_number", "A", 3, confidence=Confidence.LOW)]
    out = gate.run(findings=findings, warnings=[], bundle=_bundle())
    assert len(out["audits"]) == 1
    audit = out["audits"][0]
    assert audit.verdict is None
    assert audit.judge_failed is True


def test_audit_index_matches_original_finding_position() -> None:
    """Audit's finding_index points back into the input findings list."""
    llm = FakeLLM(canned={"IdentifierVerdict": _drop_verdict()})
    gate = IdentifierFindingGate(llm=llm)
    findings = [
        _f("style_code", "A", 3, confidence=Confidence.HIGH),       # idx 0, clean
        _f("io_number",  "B", 3, confidence=Confidence.LOW),        # idx 1, judged
        _f("color_code", "C", 3, confidence=Confidence.HIGH),       # idx 2, clean
    ]
    out = gate.run(findings=findings, warnings=[], bundle=_bundle())
    assert len(out["audits"]) == 1
    assert out["audits"][0].finding_index == 1


# ─── Component plumbing ──────────────────────────────────────────────────


def test_gate_sockets_registered() -> None:
    gate = IdentifierFindingGate(llm=FakeLLM(canned={}))
    inputs = gate.__haystack_input__._sockets_dict
    assert "findings" in inputs
    assert "warnings" in inputs
    assert "bundle" in inputs
    outputs = gate.__haystack_output__._sockets_dict
    assert "findings" in outputs
    assert "audits" in outputs


def test_gate_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("judge_gate", IdentifierFindingGate(llm=FakeLLM(canned={})))
    assert "judge_gate" in pipeline.graph.nodes
