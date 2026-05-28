"""StageSequenceValidator — per-PLI stage plan_date order check."""
from __future__ import annotations

import datetime as dt

from haystack import Pipeline

from app.components.validators.stage_sequence import StageSequenceValidator
from app.specs.schemas import FinalStage


def _stage(canonical: str | None, plan_date: dt.date | None, *, name: str | None = None) -> FinalStage:
    return FinalStage(
        name=name or canonical or "Unknown",
        canonical=canonical,
        plan_date=plan_date,
        plan_date_col=1,
        column_range=(1, 1),
        stage_metadata={},
    )


# ─── Happy path ───────────────────────────────────────────────────────────


def test_chronological_stages_yield_no_warnings() -> None:
    """fabric (early) → cutting (middle) → final_inspection (late) → ex_factory (late)."""
    stages_per_row = {
        3: [
            _stage("fabric",              dt.date(2026, 5, 1)),
            _stage("cutting",             dt.date(2026, 5, 15)),
            _stage("final_inspection",    dt.date(2026, 6, 10)),
            _stage("ex_factory_shipment", dt.date(2026, 6, 15)),
        ],
    }
    out = StageSequenceValidator().run(stages_per_row=stages_per_row)
    assert out["warnings"] == []


def test_equal_plan_dates_yield_no_warnings() -> None:
    """Equal dates between adjacent stages aren't inversions."""
    same = dt.date(2026, 5, 1)
    stages_per_row = {
        3: [
            _stage("fabric", same),
            _stage("cutting", same),
        ],
    }
    assert StageSequenceValidator().run(stages_per_row=stages_per_row)["warnings"] == []


# ─── Inversion cases ──────────────────────────────────────────────────────


def test_cross_bucket_inversion_emits_warning() -> None:
    """final_inspection (late) before fabric (early) → catalog inversion."""
    stages_per_row = {
        3: [
            _stage("fabric",           dt.date(2026, 6, 1)),     # late by date
            _stage("final_inspection", dt.date(2026, 5, 1)),     # early by date
        ],
    }
    out = StageSequenceValidator().run(stages_per_row=stages_per_row)
    assert len(out["warnings"]) == 1
    w = out["warnings"][0]
    assert w.name == "stage_sequence_inversion"
    assert w.severity == "warning"
    assert "fabric" in w.message
    assert "final_inspection" in w.message
    assert "row 3" in w.message


def test_within_bucket_inversion_emits_warning() -> None:
    """Two middle-bucket stages out of catalog order also warn (consecutive pair walk)."""
    stages_per_row = {
        3: [
            _stage("cutting", dt.date(2026, 6, 1)),
            _stage("sewing",  dt.date(2026, 5, 1)),  # sewing comes after cutting in catalog
        ],
    }
    out = StageSequenceValidator().run(stages_per_row=stages_per_row)
    inversions = [w for w in out["warnings"] if w.name == "stage_sequence_inversion"]
    assert len(inversions) == 1


# ─── Multi-row scenarios ──────────────────────────────────────────────────


def test_warnings_only_on_offending_rows() -> None:
    stages_per_row = {
        3: [   # valid
            _stage("fabric",  dt.date(2026, 5, 1)),
            _stage("cutting", dt.date(2026, 5, 15)),
        ],
        4: [   # inverted
            _stage("fabric",  dt.date(2026, 6, 1)),
            _stage("cutting", dt.date(2026, 5, 1)),
        ],
    }
    out = StageSequenceValidator().run(stages_per_row=stages_per_row)
    assert len(out["warnings"]) == 1
    assert "row 4" in out["warnings"][0].message


def test_rows_emitted_in_sorted_order() -> None:
    stages_per_row = {
        7: [
            _stage("fabric",  dt.date(2026, 6, 10)),
            _stage("cutting", dt.date(2026, 6, 1)),
        ],
        3: [
            _stage("fabric",  dt.date(2026, 5, 10)),
            _stage("cutting", dt.date(2026, 5, 1)),
        ],
    }
    out = StageSequenceValidator().run(stages_per_row=stages_per_row)
    rows = [int(w.message.split("row ")[1].split(":")[0]) for w in out["warnings"]]
    assert rows == sorted(rows)


# ─── Filter cases ─────────────────────────────────────────────────────────


def test_stage_with_canonical_none_is_skipped() -> None:
    """Novel (open-vocab) stages don't trigger validation — no priority info."""
    stages_per_row = {
        3: [
            _stage("fabric",  dt.date(2026, 6, 1)),
            _stage(None,      dt.date(2026, 5, 1), name="Some Custom Stage"),
        ],
    }
    out = StageSequenceValidator().run(stages_per_row=stages_per_row)
    assert out["warnings"] == []


def test_stage_with_no_plan_date_skipped() -> None:
    """A stage carrying only metadata (no plan_date) can't be sequence-checked."""
    stages_per_row = {
        3: [
            _stage("fabric",  dt.date(2026, 6, 1)),
            _stage("cutting", None),
        ],
    }
    out = StageSequenceValidator().run(stages_per_row=stages_per_row)
    assert out["warnings"] == []


def test_single_stage_per_pli_no_warnings() -> None:
    """Nothing to compare against."""
    stages_per_row = {
        3: [_stage("fabric", dt.date(2026, 5, 1))],
    }
    assert StageSequenceValidator().run(stages_per_row=stages_per_row)["warnings"] == []


# ─── Degenerate inputs ────────────────────────────────────────────────────


def test_empty_input_yields_no_warnings() -> None:
    assert StageSequenceValidator().run(stages_per_row={})["warnings"] == []


def test_row_with_empty_stage_list_no_warnings() -> None:
    assert StageSequenceValidator().run(stages_per_row={3: []})["warnings"] == []


# ─── Component plumbing ──────────────────────────────────────────────────


def test_validator_sockets_registered() -> None:
    comp = StageSequenceValidator()
    assert "stages_per_row" in comp.__haystack_input__._sockets_dict
    assert "warnings" in comp.__haystack_output__._sockets_dict


def test_validator_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("stage_seq", StageSequenceValidator())
    assert "stage_seq" in pipeline.graph.nodes
