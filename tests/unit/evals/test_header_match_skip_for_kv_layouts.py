"""header_match returns 1.0 for non-row_per_pli layouts (skip, doesn't apply)."""
from app.models.extraction import ExtractionResult
from evals.scorers.header_match import score_header_match


class _Stub:
    pass


def test_sheet_is_pli_skips_to_one() -> None:
    actual = ExtractionResult(plis=[], format_detected="sheet_is_pli")
    assert score_header_match(actual, _Stub()) == 1.0


def test_section_per_pli_skips_to_one() -> None:
    actual = ExtractionResult(plis=[], format_detected="section_per_pli")
    assert score_header_match(actual, _Stub()) == 1.0


def test_row_per_pli_runs_existing_logic_no_plis() -> None:
    # No PLIs → existing return 1.0 (no headers to check).
    actual = ExtractionResult(plis=[], format_detected="row_per_pli")
    assert score_header_match(actual, _Stub()) == 1.0
