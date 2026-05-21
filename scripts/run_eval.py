"""make eval entrypoint — run extractor over labeled corpus and print matrix.

Usage:
    make eval                # full corpus
    make eval-smoke          # 7-file smoke subset (fast iteration)
or directly, after activating the venv (`.venv/Scripts/activate` on Windows
or `source .venv/bin/activate` on macOS/Linux):
    python scripts/run_eval.py
    python scripts/run_eval.py --smoke

To re-score frozen outputs from a prior run without re-extracting:
    python scripts/run_eval.py --replay evals/runs/<utc>/outputs/
    python scripts/run_eval.py --replay evals/runs/<utc>/outputs/ --smoke
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Ensure repo root is importable when invoked as `python scripts/run_eval.py`.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.pipelines.extract import extract as _orchestrator_extract
from evals._label_dir import LABELS_DIR
from evals._smoke_subset import SMOKE_SUBSET
from evals._workbook_dir import WORKBOOKS_DIR
from evals.evaluator import evaluate
from evals.matrix import render_matrix


class TnaServiceExtractor:
    """Adapter — exposes orchestrator.extract via ExtractorProtocol."""

    def extract(self, workbook_path: Path):
        return _orchestrator_extract(workbook_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TNA extractor eval.")
    parser.add_argument(
        "--replay", type=Path, default=None,
        help="Path to a prior run's outputs/ directory. Re-scores against "
             "frozen ExtractionResult JSONs; no live extraction.",
    )
    parser.add_argument(
        "--smoke", action="store_true",
        help="Restrict to the 7-file smoke subset (see evals/_smoke_subset.py). "
             "Pairs with --replay or runs live extraction on just those files.",
    )
    args = parser.parse_args()

    file_stems = SMOKE_SUBSET if args.smoke else None
    runs_dir = ROOT / "evals" / "runs"
    if args.replay is not None:
        from evals.evaluator import evaluate_replay
        rows = evaluate_replay(
            replay_outputs_dir=args.replay,
            labels_dir=LABELS_DIR, workbooks_dir=WORKBOOKS_DIR,
            runs_dir=runs_dir, file_stems=file_stems,
        )
    else:
        rows = evaluate(
            extractor=TnaServiceExtractor(),
            labels_dir=LABELS_DIR,
            workbooks_dir=WORKBOOKS_DIR,
            runs_dir=runs_dir,
            file_stems=file_stems,
        )
    print(render_matrix(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
