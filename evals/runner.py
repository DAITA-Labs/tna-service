"""Eval runner — score one extractor against one labeled file."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass
from pathlib import Path
from app.models.extraction import ExtractionResult
from app.models.workbook import WorkbookCtx
from evals.interface import ExtractorProtocol
from evals.scorers.pli_recall import score_pli_recall
from evals.scorers.field_precision_recall import score_field_precision_recall
from evals.scorers.stage_recall import score_stage_recall
from evals.scorers.source_cell_match import score_source_cell_match
from evals.scorers.header_match import score_header_match


@dataclass
class EvalRow:
    file_name: str
    pli_recall: float
    field_precision: float
    field_recall: float
    stage_recall: float
    source_cell_match: float
    header_match: float
    duration_seconds: float
    retry_count: int = 0


def _load_label(path: Path) -> ExtractionResult:
    return ExtractionResult(**json.loads(path.read_text(encoding="utf-8")))


def run_one(
    *, extractor: ExtractorProtocol,
    workbook_path: Path, label_path: Path,
    ctx: WorkbookCtx | None = None,
) -> EvalRow:
    expected = _load_label(label_path)
    t0 = time.monotonic()
    actual = extractor.extract(workbook_path)
    duration = time.monotonic() - t0

    pli_r = score_pli_recall(actual, expected)
    prec, rec = score_field_precision_recall(actual, expected)
    stg_r = score_stage_recall(actual, expected)
    src = score_source_cell_match(actual, ctx) if ctx else 0.0
    hdr = score_header_match(actual, ctx) if ctx else 0.0

    return EvalRow(
        file_name=label_path.stem,
        pli_recall=round(pli_r, 4),
        field_precision=round(prec, 4),
        field_recall=round(rec, 4),
        stage_recall=round(stg_r, 4),
        source_cell_match=round(src, 4),
        header_match=round(hdr, 4),
        duration_seconds=round(duration, 1),
    )
