"""Stage recall — for matched PLI pairs, fraction of expected stages
(matched by name, case-insensitive)."""
from __future__ import annotations
from app.models.extraction import ExtractionResult
from evals.scorers.pli_recall import match_pli_pairs


def score_stage_recall(actual: ExtractionResult, expected: ExtractionResult) -> float:
    pairs = match_pli_pairs(actual, expected)
    total = 0
    matched = 0
    for exp_idx, act_idx in pairs:
        exp_stages = expected.plis[exp_idx].stages
        if act_idx is None:
            total += len(exp_stages)
            continue
        act_names = {s.name.lower().strip() for s in actual.plis[act_idx].stages}
        for st in exp_stages:
            total += 1
            if st.name.lower().strip() in act_names:
                matched += 1
    return matched / total if total else 1.0
