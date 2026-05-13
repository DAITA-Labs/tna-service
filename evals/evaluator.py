"""Top-level evaluator — iterate all labeled files, collect EvalRows, write history."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from app.repositories.workbook_repo import register_workbook
from evals.interface import ExtractorProtocol
from evals.runner import EvalRow, run_one


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
        ctx = register_workbook(wb_path)
        row = run_one(extractor=extractor, workbook_path=wb_path,
                     label_path=label_path, ctx=ctx)
        rows.append(row)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = runs_dir / f"{ts}.json"
    out.write_text(json.dumps([r.__dict__ for r in rows], indent=2),
                   encoding="utf-8")
    return rows
