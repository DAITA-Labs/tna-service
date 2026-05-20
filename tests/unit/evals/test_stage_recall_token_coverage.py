"""stage_recall now scores by token coverage, not exact match."""
from evals.scorers.stage_recall import _label_token_coverage


def test_exact_canonical_match() -> None:
    assert _label_token_coverage("Sewing Start", {"sewing_start"}) == 1.0


def test_multi_word_label_to_underscored_canonical() -> None:
    assert _label_token_coverage("Trims Inhouse", {"trims_inhouse"}) == 1.0


def test_partial_coverage_canonical_loses_a_token() -> None:
    # "Ex Factory Shipment" has 3 tokens; canonical "ex_factory" matches 2.
    assert _label_token_coverage("Ex Factory Shipment", {"ex_factory"}) == 2 / 3


def test_abbreviation_against_full_canonical() -> None:
    # Label "FI" → token "fi" is a substring of "final_inspection".
    assert _label_token_coverage("FI", {"final_inspection"}) == 1.0


def test_unrelated_label_scores_zero() -> None:
    # Label "PPS Submission" → tokens "pps", "submission". Neither appears in
    # any canonical we'd extract for this concept.
    assert _label_token_coverage("PPS Submission", {"pre_production_send"}) == 0.0


def test_picks_max_across_multiple_extracted() -> None:
    # Best match wins. "Sewing" → tokens ["sewing"] matches both "sewing" and
    # "sewing_start" at 1.0 — either is fine; coverage caps at 1.0.
    assert _label_token_coverage("Sewing", {"sewing_start", "feeding"}) == 1.0


def test_empty_label_returns_zero() -> None:
    assert _label_token_coverage("", {"cutting"}) == 0.0


def test_empty_extracted_returns_zero() -> None:
    assert _label_token_coverage("Cutting", set()) == 0.0
