"""Tests for evals/scorers/*."""
from app.models.extraction import PLI, Stage, ExtractionResult
from evals.scorers.pli_recall import score_pli_recall
from evals.scorers.field_precision_recall import score_field_precision_recall
from evals.scorers.stage_recall import score_stage_recall


def test_pli_recall_one_to_one_match():
    expected = ExtractionResult(plis=[
        PLI(io_number="1", style_code="A", color_code="RED"),
        PLI(io_number="2", style_code="B", color_code="BLUE"),
    ])
    actual = ExtractionResult(plis=[
        PLI(io_number="1", style_code="A", color_code="RED"),
        PLI(io_number="2", style_code="B", color_code="BLUE"),
    ])
    assert score_pli_recall(actual, expected) == 1.0


def test_pli_recall_partial():
    expected = ExtractionResult(plis=[
        PLI(io_number="1", style_code="A"),
        PLI(io_number="2", style_code="B"),
    ])
    actual = ExtractionResult(plis=[
        PLI(io_number="1", style_code="A"),
    ])
    assert score_pli_recall(actual, expected) == 0.5


def test_field_precision_recall():
    expected = ExtractionResult(plis=[PLI(io_number="1", style_code="A",
                                          color_code="RED", quantity=10)])
    actual = ExtractionResult(plis=[PLI(io_number="1", style_code="A",
                                        color_code="RED", quantity=99)])
    prec, rec = score_field_precision_recall(actual, expected)
    assert prec == 0.75
    assert rec == 0.75


def test_stage_recall():
    expected = ExtractionResult(plis=[
        PLI(io_number="1", stages=[Stage(name="Sewing"), Stage(name="Inspection")]),
    ])
    actual = ExtractionResult(plis=[
        PLI(io_number="1", stages=[Stage(name="Sewing")]),
    ])
    assert score_stage_recall(actual, expected) == 0.5
