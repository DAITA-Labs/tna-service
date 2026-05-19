"""evaluator.evaluate isolates per-file failures and continues the batch."""
import json
from pathlib import Path

from app.models.extraction import ExtractionResult
from evals.evaluator import evaluate


class _CrashOnExtract:
    """Extractor that raises on every workbook — proves the wrap catches it."""
    def extract(self, path: Path) -> ExtractionResult:
        raise RuntimeError("simulated extractor crash")


class _OkExtractor:
    """Extractor that returns an empty ExtractionResult — proves success rows still work."""
    def extract(self, path: Path) -> ExtractionResult:
        return ExtractionResult(plis=[], source_file=str(path))


def _make_label(labels_dir: Path, stem: str) -> None:
    labels_dir.mkdir(parents=True, exist_ok=True)
    (labels_dir / f"{stem}.json").write_text(json.dumps({
        "plis": [], "source_file": f"{stem}.xlsx",
    }), encoding="utf-8")


def _make_workbook(workbooks_dir: Path, stem: str) -> None:
    import openpyxl
    workbooks_dir.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    wb.active.title = "S"
    wb.save(workbooks_dir / f"{stem}.xlsx")


def test_per_file_extractor_crash_does_not_abort_batch(tmp_path) -> None:
    labels_dir = tmp_path / "labels"
    workbooks_dir = tmp_path / "workbooks"
    runs_dir = tmp_path / "runs"

    _make_label(labels_dir, "a")
    _make_label(labels_dir, "b")
    _make_workbook(workbooks_dir, "a")
    _make_workbook(workbooks_dir, "b")

    rows = evaluate(extractor=_CrashOnExtract(), labels_dir=labels_dir,
                    workbooks_dir=workbooks_dir, runs_dir=runs_dir)
    # 2 labels exist, both should have rows even though the extractor crashed.
    assert len(rows) == 2
    assert all(r.error and "simulated extractor crash" in r.error for r in rows)
    assert all(r.pli_recall == 0.0 for r in rows)
    # The runs file got written.
    runs = list(runs_dir.glob("*.json"))
    assert len(runs) == 1


def test_successful_extraction_row_has_no_error(tmp_path) -> None:
    labels_dir = tmp_path / "labels"
    workbooks_dir = tmp_path / "workbooks"
    runs_dir = tmp_path / "runs"

    _make_label(labels_dir, "a")
    _make_workbook(workbooks_dir, "a")

    rows = evaluate(extractor=_OkExtractor(), labels_dir=labels_dir,
                    workbooks_dir=workbooks_dir, runs_dir=runs_dir)
    assert len(rows) == 1
    assert rows[0].error is None
