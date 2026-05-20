"""Stage recall — for matched PLI pairs, partial credit by token coverage."""
from __future__ import annotations
from app.models.extraction import ExtractionResult
from evals.scorers.pli_recall import match_pli_pairs


def _label_token_coverage(label_name: str, extracted_names: set[str]) -> float:
    """Fraction of label-name tokens contained as substrings in any extracted stage name.

    Tokenizes the label name on whitespace, lowercases each token, and for each
    extracted stage name counts how many tokens appear as substrings. Returns
    the maximum coverage (0.0-1.0) across all extracted names.

    Captures partial credit when the extractor's canonical (e.g. "sewing_start")
    contains the label's tokens (e.g. "Sewing Start" → ["sewing", "start"]).
    """
    tokens = label_name.lower().split()
    if not tokens:
        return 0.0
    best = 0.0
    for ext_name in extracted_names:
        ext_lower = ext_name.lower()
        matched = sum(1 for t in tokens if t in ext_lower)
        coverage = matched / len(tokens)
        if coverage > best:
            best = coverage
            if best == 1.0:
                break
    return best


def score_stage_recall(actual: ExtractionResult, expected: ExtractionResult) -> float:
    """Score stage recall as the mean per-stage token-coverage across matched PLI pairs."""
    pairs = match_pli_pairs(actual, expected)
    total = 0
    score = 0.0
    for exp_idx, act_idx in pairs:
        exp_stages = expected.plis[exp_idx].stages
        if act_idx is None:
            total += len(exp_stages)
            continue
        act_names = {s.name for s in actual.plis[act_idx].stages if s.name}
        for st in exp_stages:
            total += 1
            score += _label_token_coverage(st.name, act_names)
    return score / total if total else 1.0
