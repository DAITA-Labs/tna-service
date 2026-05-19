"""Top-level evaluator — iterate all labeled files, collect EvalRows, write history."""
from __future__ import annotations
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
    runs_dir.mkdir(parents=True, exist_ok=True)
    rows: list[EvalRow] = []
    for label_path in sorted(labels_dir.glob("*.json")):
        wb_path = workbooks_dir / f"{label_path.stem}.xlsx"
        if not wb_path.exists():
            continue
        t0 = time.monotonic()
        try:
            ctx = register_workbook(wb_path)
            row = run_one(extractor=extractor, workbook_path=wb_path,
                         label_path=label_path, ctx=ctx)
        except Exception as exc:  # noqa: BLE001 — isolate per-file failures
            duration = time.monotonic() - t0
            error_msg = f"{type(exc).__name__}: {exc}"
            log.warning("eval_per_file_failure file=%s error=%s",
                        label_path.stem, error_msg)
            row = failed_row(
                file_name=label_path.stem, error=error_msg,
                duration_seconds=duration,
            )
        rows.append(row)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = runs_dir / f"{ts}.json"
    out.write_text(json.dumps([r.__dict__ for r in rows], indent=2),
                   encoding="utf-8")
    return rows
