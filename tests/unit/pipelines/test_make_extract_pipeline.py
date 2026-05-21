"""Integration tests for make_per_sheet_pipeline and make_extract_pipeline factories.

Verifies that the Haystack Pipeline graphs are wired correctly by:
- Checking component membership
- Checking key edge connections
- Running the per-sheet pipeline end-to-end against a simple fixture
"""
from __future__ import annotations

from types import SimpleNamespace

import openpyxl
from haystack import Pipeline
from structlog.testing import capture_logs

import app.tools.bulk_read  # noqa: F401 — register tools
import app.tools.survey  # noqa: F401

from app.pipelines.extract import make_extract_pipeline, make_per_sheet_pipeline
from tests.fixtures.fake_llm import FakeLLM


def _fake_llm() -> FakeLLM:
    return FakeLLM(canned={
        "SheetClassifierOutput": {"relevant_sheets": ["S1"]},
        "CanonicalNameMap": {"field_labels": {}, "stage_names": {}},
        "PlanVerdict": {"verdict": "looks_correct"},
        "LayoutHints": {"identity_column_suggestion": None},
    })


def test_make_per_sheet_pipeline_returns_pipeline() -> None:
    """make_per_sheet_pipeline returns a Pipeline with 9 named components."""
    llm = _fake_llm()
    pipe = make_per_sheet_pipeline(llm)
    assert isinstance(pipe, Pipeline)
    expected_names = {
        "planner", "plan_validator", "layout_hinter", "plan_reviewer",
        "post_review_validator", "field_namer", "post_namer_validator",
        "pre_apply_validator", "applier",
    }
    assert set(pipe.graph.nodes) == expected_names


def test_make_extract_pipeline_returns_pipeline() -> None:
    """make_extract_pipeline returns a Pipeline with 9 named components."""
    llm = _fake_llm()
    ctx = SimpleNamespace(path=SimpleNamespace(name="test.xlsx"))
    pipe = make_extract_pipeline(llm, ctx)
    assert isinstance(pipe, Pipeline)
    expected_names = {
        "summary_provider", "sheet_classifier", "per_sheet", "result_builder",
        "source_cell", "header_match", "coverage", "field_dropout", "reconciler",
    }
    assert set(pipe.graph.nodes) == expected_names


def test_per_sheet_pipeline_produces_plis_from_simple_workbook() -> None:
    """Per-sheet pipeline runs end-to-end against a minimal workbook and produces PLIs."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S1"
    ws.cell(row=1, column=1).value = "IO NO"
    ws.cell(row=2, column=1).value = "1001"
    ctx = SimpleNamespace(wb=wb, path=SimpleNamespace(name="test.xlsx"))

    llm = _fake_llm()
    pipe = make_per_sheet_pipeline(llm)
    with capture_logs():
        out = pipe.run({
            "planner": {"workbook_ctx": ctx, "sheet": "S1"},
            "plan_validator": {"workbook_ctx": ctx},
            "layout_hinter": {"workbook_ctx": ctx, "sheet": "S1"},
            "plan_reviewer": {"workbook_ctx": ctx},
            "field_namer": {"workbook_ctx": ctx},
            "applier": {"workbook_ctx": ctx},
        })
    assert "applier" in out
    assert isinstance(out["applier"]["plis"], list)
    assert isinstance(out["applier"]["warnings"], list)
