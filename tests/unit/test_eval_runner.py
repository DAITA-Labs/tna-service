"""Tests for evals/runner + evals/matrix."""
import json
from pathlib import Path
from app.models.extraction import ExtractionResult, PLI
from evals.runner import EvalRow, run_one
from evals.matrix import render_matrix


class FakeExtractor:
    def __init__(self, plis):
        self.plis = plis

    def extract(self, _path):
        return ExtractionResult(plis=self.plis)


def test_run_one_returns_row(tmp_path):
    label = {
        "plis": [{"io_number": "1"}, {"io_number": "2"}],
        "warnings": [], "format_detected": "tabular",
    }
    lp = tmp_path / "x.json"
    lp.write_text(json.dumps(label), encoding="utf-8")
    extractor = FakeExtractor(plis=[PLI(io_number="1")])
    row = run_one(extractor=extractor, workbook_path=Path("ignored"),
                 label_path=lp, ctx=None)
    assert isinstance(row, EvalRow)
    assert row.pli_recall == 0.5
    assert row.file_name == "x"


def test_render_matrix_outputs_table():
    rows = [
        EvalRow(file_name="a", pli_recall=1.0, field_precision=1.0,
                field_recall=1.0, stage_recall=1.0, source_cell_match=1.0,
                header_match=1.0, duration_seconds=10.0, retry_count=0),
        EvalRow(file_name="b", pli_recall=0.5, field_precision=0.8,
                field_recall=0.6, stage_recall=0.7, source_cell_match=0.9,
                header_match=0.95, duration_seconds=15.0, retry_count=1),
    ]
    text = render_matrix(rows)
    assert "pli_rec" in text
    assert "a" in text and "b" in text
