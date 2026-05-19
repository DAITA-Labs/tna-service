"""evaluator.evaluate writes per-run nested dir with matrix + per-file outputs + log."""
import json
from pathlib import Path

import openpyxl

from app.models.extraction import ExtractionResult, PLI
from evals.evaluator import evaluate


class _ExtractorReturnsOne:
    """Returns one PLI per file with the file stem as io_number — easy to verify."""
    def extract(self, path: Path) -> ExtractionResult:
        stem = path.stem
        return ExtractionResult(
            plis=[PLI(io_number=stem)],
            source_file=str(path),
        )


def _make_label(labels_dir: Path, stem: str) -> None:
    labels_dir.mkdir(parents=True, exist_ok=True)
    (labels_dir / f"{stem}.json").write_text(json.dumps({
        "plis": [{"io_number": stem}],
        "source_file": f"{stem}.xlsx",
    }), encoding="utf-8")


def _make_workbook(workbooks_dir: Path, stem: str) -> None:
    workbooks_dir.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    wb.active.title = "S"
    wb.save(workbooks_dir / f"{stem}.xlsx")


def test_evaluate_writes_nested_run_dir(tmp_path) -> None:
    labels_dir = tmp_path / "labels"
    workbooks_dir = tmp_path / "workbooks"
    runs_dir = tmp_path / "runs"
    for stem in ("alpha", "beta"):
        _make_label(labels_dir, stem)
        _make_workbook(workbooks_dir, stem)

    rows = evaluate(extractor=_ExtractorReturnsOne(), labels_dir=labels_dir,
                    workbooks_dir=workbooks_dir, runs_dir=runs_dir)

    assert len(rows) == 2

    # Exactly one per-run subdir.
    run_dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    # matrix.json carries the scoreboard.
    matrix_path = run_dir / "matrix.json"
    assert matrix_path.exists()
    matrix = json.loads(matrix_path.read_text())
    assert len(matrix) == 2
    assert {row["file_name"] for row in matrix} == {"alpha", "beta"}

    # outputs/<stem>.json per file — round-trippable into ExtractionResult.
    outputs_dir = run_dir / "outputs"
    assert outputs_dir.is_dir()
    for stem in ("alpha", "beta"):
        out_path = outputs_dir / f"{stem}.json"
        assert out_path.exists(), f"missing {out_path}"
        actual = ExtractionResult(**json.loads(out_path.read_text()))
        assert actual.plis[0].io_number == stem

    # eval.log exists (may be empty for this no-warning-emitting test).
    log_path = run_dir / "eval.log"
    assert log_path.exists()


def test_evaluate_per_file_failure_still_writes_log_and_skipped_output(tmp_path) -> None:
    """When a file crashes, the per-file output is omitted but the row + log + matrix persist."""
    class _CrashOnExtract:
        def extract(self, path: Path) -> ExtractionResult:
            raise RuntimeError("simulated crash")

    labels_dir = tmp_path / "labels"
    workbooks_dir = tmp_path / "workbooks"
    runs_dir = tmp_path / "runs"
    _make_label(labels_dir, "boom")
    _make_workbook(workbooks_dir, "boom")

    rows = evaluate(extractor=_CrashOnExtract(), labels_dir=labels_dir,
                    workbooks_dir=workbooks_dir, runs_dir=runs_dir)

    assert len(rows) == 1
    assert rows[0].error and "simulated crash" in rows[0].error

    run_dir = next(p for p in runs_dir.iterdir() if p.is_dir())
    assert (run_dir / "matrix.json").exists()
    assert (run_dir / "eval.log").exists()
    # No output JSON for the crashed file — extraction never produced one.
    assert not (run_dir / "outputs" / "boom.json").exists()
