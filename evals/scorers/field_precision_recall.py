"""Field precision + recall over canonical fields, scoped to matched PLIs."""
from __future__ import annotations
from app.models.extraction import ExtractionResult
from evals.scorers.pli_recall import match_pli_pairs


_FIELDS = ("io_number", "style_code", "style_name", "color_code",
           "color_name", "fabric_code", "delivery_date", "quantity")


def score_field_precision_recall(
    actual: ExtractionResult, expected: ExtractionResult,
) -> tuple[float, float]:
    pairs = match_pli_pairs(actual, expected)
    tp = 0
    actual_emitted = 0
    expected_count = 0
    for exp_idx, act_idx in pairs:
        exp = expected.plis[exp_idx]
        if act_idx is None:
            for f in _FIELDS:
                if getattr(exp, f, None) is not None:
                    expected_count += 1
            continue
        act = actual.plis[act_idx]
        for f in _FIELDS:
            exp_v = getattr(exp, f, None)
            act_v = getattr(act, f, None)
            if exp_v is not None:
                expected_count += 1
            if act_v is not None:
                actual_emitted += 1
            if exp_v is not None and act_v == exp_v:
                tp += 1
    precision = tp / actual_emitted if actual_emitted else 0.0
    recall = tp / expected_count if expected_count else 1.0
    return precision, recall
