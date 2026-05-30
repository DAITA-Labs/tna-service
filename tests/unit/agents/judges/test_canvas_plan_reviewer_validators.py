"""CanvasPlanReviewer semantic validators."""
from __future__ import annotations

from app.agents._base import _OutputState
from app.agents.judges.canvas_plan_reviewer.schema import (
    CanonicalRepick,
    PlanReviewVerdict,
)
from app.agents.judges.canvas_plan_reviewer.validators import (
    validate_plan_review_verdict,
)


def _verdict(**kw) -> PlanReviewVerdict:
    base = {"decision": "approve", "reason": "ok", "confidence": "high"}
    base.update(kw)
    return PlanReviewVerdict(**base)


def test_approve_with_no_repicks_is_ok() -> None:
    out = validate_plan_review_verdict(_verdict(), None)
    assert out.state is _OutputState.OK


def test_repick_without_repicks_retries() -> None:
    out = validate_plan_review_verdict(_verdict(decision="repick"), None)
    assert out.state is _OutputState.RETRY


def test_approve_with_repicks_retries() -> None:
    r = CanonicalRepick(canonical="io_number", mode="column", column=2)
    out = validate_plan_review_verdict(_verdict(repicks=[r]), None)
    assert out.state is _OutputState.RETRY


def test_column_mode_missing_column_retries() -> None:
    r = CanonicalRepick(canonical="io_number", mode="column")
    out = validate_plan_review_verdict(
        _verdict(decision="repick", repicks=[r]), None,
    )
    assert out.state is _OutputState.RETRY


def test_column_mode_with_row_retries() -> None:
    r = CanonicalRepick(canonical="io_number", mode="column", column=2, row=3)
    out = validate_plan_review_verdict(
        _verdict(decision="repick", repicks=[r]), None,
    )
    assert out.state is _OutputState.RETRY


def test_kv_block_mode_with_label_coord_is_ok() -> None:
    r = CanonicalRepick(
        canonical="style_code", mode="kv_block", kv_label_coord=("A", 2),
    )
    out = validate_plan_review_verdict(
        _verdict(decision="repick", repicks=[r]), None,
    )
    assert out.state is _OutputState.OK


def test_kv_block_mode_with_column_retries() -> None:
    r = CanonicalRepick(
        canonical="style_code", mode="kv_block",
        kv_label_coord=("A", 2), column=5,
    )
    out = validate_plan_review_verdict(
        _verdict(decision="repick", repicks=[r]), None,
    )
    assert out.state is _OutputState.RETRY


def test_row_mode_requires_row() -> None:
    r = CanonicalRepick(canonical="io_number", mode="row")
    out = validate_plan_review_verdict(
        _verdict(decision="repick", repicks=[r]), None,
    )
    assert out.state is _OutputState.RETRY
