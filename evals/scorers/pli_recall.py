"""PLI recall + matching helper.

Match strategy: compound-key, strongest first — (io,style,color) → (io,style)
→ (io). One-to-one assignment via consumption tracking so duplicate ios in
the expected list don't collapse onto the same actual PLI.
"""
from __future__ import annotations
from app.models.extraction import ExtractionResult, PLI


def _match(actual: list[PLI], expected: PLI, consumed: set[int]) -> int | None:
    candidates = [(i, p) for i, p in enumerate(actual) if i not in consumed]
    for i, p in candidates:
        if (expected.io_number and p.io_number == expected.io_number
                and expected.style_code and p.style_code == expected.style_code
                and expected.color_code and p.color_code == expected.color_code):
            return i
    for i, p in candidates:
        if (expected.io_number and p.io_number == expected.io_number
                and expected.style_code and p.style_code == expected.style_code):
            return i
    for i, p in candidates:
        if expected.io_number and p.io_number == expected.io_number:
            return i
    return None


def score_pli_recall(actual: ExtractionResult, expected: ExtractionResult) -> float:
    if not expected.plis:
        return 1.0
    consumed: set[int] = set()
    matched = 0
    for exp in expected.plis:
        idx = _match(actual.plis, exp, consumed)
        if idx is not None:
            consumed.add(idx)
            matched += 1
    return matched / len(expected.plis)


def match_pli_pairs(actual: ExtractionResult, expected: ExtractionResult):
    """Return list of (expected_idx, actual_idx | None)."""
    consumed: set[int] = set()
    pairs = []
    for i, exp in enumerate(expected.plis):
        idx = _match(actual.plis, exp, consumed)
        if idx is not None:
            consumed.add(idx)
        pairs.append((i, idx))
    return pairs
