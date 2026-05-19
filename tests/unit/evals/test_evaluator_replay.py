"""evaluator.evaluate_replay re-scores against frozen outputs without an extractor."""
import json
from pathlib import Path

import openpyxl

from app.models.extraction import ExtractionResult, PLI
from evals.evaluator import evaluate, evaluate_replay


class _ExtractorReturnsOne:
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


def _live_run(tmp_path: Path) -> Path:
    """Helper: produce a live-run dir with outputs/<stem>.json for two stems."""
    labels_dir = tmp_path / "labels"
    workbooks_dir = tmp_path / "workbooks"
    runs_dir = tmp_path / "runs"
    for stem in ("alpha", "beta"):
        _make_label(labels_dir, stem)
        _make_workbook(workbooks_dir, stem)
    evaluate(extractor=_ExtractorReturnsOne(), labels_dir=labels_dir,
             workbooks_dir=workbooks_dir, runs_dir=runs_dir)
    run_dir = next(p for p in runs_dir.iterdir() if p.is_dir())
    return run_dir


def test_replay_reproduces_live_matrix(tmp_path) -> None:
    """Replay against a live run's outputs must reproduce the same per-file scores."""
    live_run_dir = _live_run(tmp_path)

    labels_dir = tmp_path / "labels"
    workbooks_dir = tmp_path / "workbooks"
    replay_runs_dir = tmp_path / "replay-runs"

    replay_rows = evaluate_replay(
        replay_outputs_dir=live_run_dir / "outputs",
        labels_dir=labels_dir, workbooks_dir=workbooks_dir,
        runs_dir=replay_runs_dir,
    )

    assert len(replay_rows) == 2
    by_file = {r.file_name: r for r in replay_rows}
    assert by_file["alpha"].pli_recall == 1.0
    assert by_file["beta"].pli_recall == 1.0
    # Replay rows have duration_seconds == 0.0 (no extraction).
    assert all(r.duration_seconds == 0.0 for r in replay_rows)
    # Replay run dir is suffixed -replay.
    replay_dir = next(p for p in replay_runs_dir.iterdir() if p.is_dir())
    assert replay_dir.name.endswith("-replay")
    # Replay produces a matrix.json and an eval.log.
    assert (replay_dir / "matrix.json").exists()
    assert (replay_dir / "eval.log").exists()


def test_replay_skips_missing_outputs(tmp_path) -> None:
    """If a label has no corresponding frozen output JSON, replay skips that label."""
    labels_dir = tmp_path / "labels"
    workbooks_dir = tmp_path / "workbooks"
    runs_dir = tmp_path / "runs"
    _make_label(labels_dir, "alpha")
    _make_label(labels_dir, "beta")
    _make_workbook(workbooks_dir, "alpha")
    _make_workbook(workbooks_dir, "beta")

    # Only alpha has a frozen output.
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    (outputs_dir / "alpha.json").write_text(
        ExtractionResult(plis=[PLI(io_number="alpha")], source_file="alpha.xlsx")
            .model_dump_json(indent=2),
        encoding="utf-8",
    )

    rows = evaluate_replay(
        replay_outputs_dir=outputs_dir, labels_dir=labels_dir,
        workbooks_dir=workbooks_dir, runs_dir=runs_dir,
    )
    # beta is skipped — only alpha appears in the replay matrix.
    assert len(rows) == 1
    assert rows[0].file_name == "alpha"


def test_replay_handles_corrupt_output_gracefully(tmp_path) -> None:
    """If a frozen output JSON is malformed, the row records error and batch continues."""
    labels_dir = tmp_path / "labels"
    workbooks_dir = tmp_path / "workbooks"
    runs_dir = tmp_path / "runs"
    _make_label(labels_dir, "broken")
    _make_workbook(workbooks_dir, "broken")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    (outputs_dir / "broken.json").write_text("{not json", encoding="utf-8")

    rows = evaluate_replay(
        replay_outputs_dir=outputs_dir, labels_dir=labels_dir,
        workbooks_dir=workbooks_dir, runs_dir=runs_dir,
    )
    assert len(rows) == 1
    assert rows[0].error
    assert rows[0].pli_recall == 0.0
