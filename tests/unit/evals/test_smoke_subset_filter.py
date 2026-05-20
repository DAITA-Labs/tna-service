"""evaluate() / evaluate_replay() honour the `file_stems` filter."""
import json
from pathlib import Path

import openpyxl

from app.models.extraction import ExtractionResult, PLI
from evals._smoke_subset import SMOKE_SUBSET
from evals.evaluator import evaluate, evaluate_replay


class _OkExtractor:
    def extract(self, path: Path) -> ExtractionResult:
        return ExtractionResult(
            plis=[PLI(io_number=path.stem)],
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


def _seed_corpus(tmp_path: Path, stems: list[str]) -> tuple[Path, Path, Path]:
    labels_dir = tmp_path / "labels"
    workbooks_dir = tmp_path / "workbooks"
    runs_dir = tmp_path / "runs"
    for stem in stems:
        _make_label(labels_dir, stem)
        _make_workbook(workbooks_dir, stem)
    return labels_dir, workbooks_dir, runs_dir


def test_evaluate_with_file_stems_filters_corpus(tmp_path) -> None:
    labels_dir, workbooks_dir, runs_dir = _seed_corpus(tmp_path, ["a", "b", "c"])

    rows = evaluate(
        extractor=_OkExtractor(),
        labels_dir=labels_dir, workbooks_dir=workbooks_dir,
        runs_dir=runs_dir, file_stems={"a", "c"},
    )
    assert {r.file_name for r in rows} == {"a", "c"}


def test_evaluate_with_file_stems_none_runs_full_corpus(tmp_path) -> None:
    labels_dir, workbooks_dir, runs_dir = _seed_corpus(tmp_path, ["a", "b", "c"])

    rows = evaluate(
        extractor=_OkExtractor(),
        labels_dir=labels_dir, workbooks_dir=workbooks_dir,
        runs_dir=runs_dir,
    )
    assert {r.file_name for r in rows} == {"a", "b", "c"}


def test_evaluate_replay_with_file_stems_filters_corpus(tmp_path) -> None:
    labels_dir, workbooks_dir, runs_dir = _seed_corpus(tmp_path, ["a", "b", "c"])
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    for stem in ("a", "b", "c"):
        (outputs_dir / f"{stem}.json").write_text(
            ExtractionResult(plis=[PLI(io_number=stem)], source_file=f"{stem}.xlsx")
                .model_dump_json(indent=2),
            encoding="utf-8",
        )

    rows = evaluate_replay(
        replay_outputs_dir=outputs_dir,
        labels_dir=labels_dir, workbooks_dir=workbooks_dir,
        runs_dir=runs_dir, file_stems={"b"},
    )
    assert {r.file_name for r in rows} == {"b"}


def test_smoke_subset_is_a_frozenset_of_seven_stems() -> None:
    assert isinstance(SMOKE_SUBSET, frozenset)
    assert len(SMOKE_SUBSET) == 7
