"""Top-level evaluator — iterate all labeled files, collect EvalRows, write history."""
from __future__ import annotations

import contextlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from app.repositories.workbook_repo import register_workbook
from evals.interface import ExtractorProtocol
from evals.runner import EvalRow, failed_row, run_one

log = logging.getLogger(__name__)


def evaluate(
    *, extractor: ExtractorProtocol,
    labels_dir: Path, workbooks_dir: Path, runs_dir: Path,
) -> list[EvalRow]:
    """Run extractor against every labeled file and write a per-run nested dir.

    Output layout (one directory per invocation):
        runs_dir / <utc>/
            matrix.json          - the EvalRow list for this run
            outputs/<stem>.json  - the ExtractionResult per evaluated file
            eval.log             - captured stdout for the run (warnings, tracebacks)

    Per-file failures are isolated: a crash records a failed_row but does not
    abort the batch. The eval.log captures all structlog/print output during
    the run so the console scoreboard at the end is the operator's primary signal.
    """
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = runs_dir / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir = run_dir / "outputs"
    matrix_path = run_dir / "matrix.json"
    log_path = run_dir / "eval.log"

    rows: list[EvalRow] = []
    with open(log_path, "w", encoding="utf-8") as log_fp:
        with contextlib.redirect_stdout(log_fp):
            for label_path in sorted(labels_dir.glob("*.json")):
                wb_path = workbooks_dir / f"{label_path.stem}.xlsx"
                if not wb_path.exists():
                    continue
                t0 = time.monotonic()
                try:
                    ctx = register_workbook(wb_path)
                    row = run_one(
                        extractor=extractor, workbook_path=wb_path,
                        label_path=label_path, ctx=ctx,
                        output_dir=outputs_dir,
                    )
                except Exception as exc:  # noqa: BLE001 — isolate per-file failures
                    duration = time.monotonic() - t0
                    error_msg = f"{type(exc).__name__}: {exc}"
                    log.warning(
                        "eval_per_file_failure file=%s error=%s",
                        label_path.stem, error_msg,
                    )
                    row = failed_row(
                        file_name=label_path.stem, error=error_msg,
                        duration_seconds=duration,
                    )
                rows.append(row)

    matrix_path.write_text(
        json.dumps([r.__dict__ for r in rows], indent=2),
        encoding="utf-8",
    )
    return rows
