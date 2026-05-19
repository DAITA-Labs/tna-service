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
    error: str | None = None


def failed_row(*, file_name: str, error: str, duration_seconds: float = 0.0) -> EvalRow:
    """Build an EvalRow representing an extraction or scoring failure.

    All metric scores are 0.0; the truncated exception message lands in `error`
    so the matrix surfaces which file crashed without aborting the batch.
    """
    return EvalRow(
        file_name=file_name,
        pli_recall=0.0, field_precision=0.0, field_recall=0.0,
        stage_recall=0.0, source_cell_match=0.0, header_match=0.0,
        duration_seconds=round(duration_seconds, 1),
        error=error[:200],
    )


def _load_label(path: Path) -> ExtractionResult:
    return ExtractionResult(**json.loads(path.read_text(encoding="utf-8")))


def _score_one(
    *, label_path: Path, actual: ExtractionResult,
    ctx: WorkbookCtx | None, duration_seconds: float,
) -> EvalRow:
    """Score an already-loaded ExtractionResult against the label at label_path."""
    expected = _load_label(label_path)
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
        duration_seconds=round(duration_seconds, 1),
    )


def run_one(
    *, extractor: ExtractorProtocol,
    workbook_path: Path, label_path: Path,
    ctx: WorkbookCtx | None = None,
    output_dir: Path | None = None,
) -> EvalRow:
    """Live run — extract, optionally archive, then score."""
    t0 = time.monotonic()
    actual = extractor.extract(workbook_path)
    duration = time.monotonic() - t0

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{label_path.stem}.json"
        out_path.write_text(actual.model_dump_json(indent=2), encoding="utf-8")

    return _score_one(label_path=label_path, actual=actual,
                      ctx=ctx, duration_seconds=duration)


def replay_one(
    *, frozen_output_path: Path, label_path: Path,
    ctx: WorkbookCtx | None = None,
) -> EvalRow:
    """Replay run — load frozen ExtractionResult and score (no extractor invocation)."""
    actual = ExtractionResult.model_validate_json(
        frozen_output_path.read_text(encoding="utf-8")
    )
    return _score_one(label_path=label_path, actual=actual,
                      ctx=ctx, duration_seconds=0.0)
