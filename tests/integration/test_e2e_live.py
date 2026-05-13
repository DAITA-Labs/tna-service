"""End-to-end tests against real Anthropic API. Gated by TNA_RUN_LIVE_TESTS=1.

Each test runs the full orchestrator on a real labeled file and asserts:
1. Numbers meet floor thresholds (regression guard).
2. The specific class-of-bug we've fixed in this project does NOT regress.
"""
import os
from pathlib import Path
import pytest

from app.services.extraction import extract
from app.repositories.workbook_repo import register_workbook
from evals.runner import run_one


_LIVE = os.environ.get("TNA_RUN_LIVE_TESTS", "0").lower() in ("1", "true", "yes")
_HAVE_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not (_LIVE and _HAVE_KEY),
                       reason="set TNA_RUN_LIVE_TESTS=1 + ANTHROPIC_API_KEY"),
]


DATASET = Path(__file__).resolve().parents[2] / "dataset"


class _Adapter:
    def extract(self, p):
        return extract(p)


def _score(stem: str):
    wb = DATASET / f"{stem}.xlsx"
    lbl = DATASET / "extracted" / f"{stem}.json"
    ctx = register_workbook(wb)
    return run_one(extractor=_Adapter(), workbook_path=wb, label_path=lbl, ctx=ctx)


def test_dkn_columnar_full_score():
    row = _score("20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS")
    assert row.pli_recall == 1.0
    assert row.field_recall >= 0.95
    assert row.stage_recall >= 0.95


def test_compass_pro_manos_field_recall_holds():
    """Regression guard for vertical_merge iteration + merge-propagation fix."""
    row = _score("20260304 MOPD W26(1) MANOS COMPASS PRO")
    assert row.pli_recall == 1.0
    assert row.field_recall >= 0.80
    assert row.stage_recall >= 0.95


def test_christian_berg_seven_plis():
    """CHRISTIAN BERG has 7 PLIs across 2 merge groups. Regression guard
    for the BoundaryFinder data_end_row spanning ALL merge groups."""
    row = _score("CHRISTIAN BERG- T&A")
    assert row.pli_recall == 1.0
    assert row.field_recall >= 0.80


def test_new_xlsx_no_duplication():
    """NEW.xlsx is 5 sheets, 5 PLIs total (one_sheet_per_pli). Regression
    guard for D3 fast-path — must NOT produce 25 duplicates."""
    row = _score("NEW")
    assert row.pli_recall == 1.0
    assert row.field_recall >= 0.75


def test_northern_reflections_filters_repeat_headers():
    """NORTHERN REFLECTIONS has 5 real PLIs + 4 repeat-header rows in the
    middle. Regression guard for the repeat-header strip in the field applier."""
    row = _score("NORTHERN REFLECTIONS- T&a")
    assert row.pli_recall == 1.0
    assert row.field_recall >= 0.60
