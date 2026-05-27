"""Similarity scoring for `SheetSignature` pairs.

`score_signatures(a, b)` returns a float in `[0, 1]`. Three orthogonal
sub-scores are combined with equal weights — together they bracket the
clusterer threshold (0.8 by design) so that minor formatting variations
within the same template land above it while genuine layout differences
fall below.

Sub-scores:

  mask_jaccard    : Jaccard overlap of the two `non_blank_mask`
                     frozensets. Captures the *shape* of populated cells
                     irrespective of contents.

  dtype_cosine    : Cosine similarity over the flattened per-row dtype
                     histograms. Captures the *ordering* of header rows
                     vs data rows.

  label_jaccard   : Jaccard overlap of `label_positions` frozensets
                     (which already carry normalised text). Captures
                     *shared header vocabulary*.

Weights bias toward mask and dtype because they're robust to data-row
content; the label signal is real but noisier (data rows can leak
strings into the label window). A sheet with no populated cells is
treated as having no template — `score_signatures` short-circuits to 0
if either signature has an empty mask.
"""
from __future__ import annotations

import math

from app.artifacts.workbook import SheetSignature


_MASK_WEIGHT = 0.4
_DTYPE_WEIGHT = 0.4
_LABEL_WEIGHT = 0.2


def score_signatures(a: SheetSignature, b: SheetSignature) -> float:
    """Return a similarity score in [0, 1] combining mask / dtype / label sub-scores."""
    if not a.non_blank_mask or not b.non_blank_mask:
        return 0.0
    mask = _jaccard(a.non_blank_mask, b.non_blank_mask)
    dtype = _dtype_cosine(a.dtype_per_row, b.dtype_per_row)
    label = _jaccard(a.label_positions, b.label_positions)
    return _MASK_WEIGHT * mask + _DTYPE_WEIGHT * dtype + _LABEL_WEIGHT * label


def _jaccard(left, right) -> float:
    """Standard Jaccard overlap; 0 when both sets are empty."""
    if not left and not right:
        return 0.0
    intersection = len(left & right)
    union = len(left | right)
    return intersection / union if union else 0.0


def _dtype_cosine(left: tuple, right: tuple) -> float:
    """Cosine similarity over flattened per-row dtype histograms.

    Pads the shorter sequence with zero-tuples so unequal-length sheets
    can still be compared — pure padding contributes nothing to the dot
    product or to either norm.
    """
    if not left and not right:
        return 0.0
    flat_a = _flatten(left)
    flat_b = _flatten(right)
    # Pad to equal length
    n = max(len(flat_a), len(flat_b))
    flat_a = flat_a + [0] * (n - len(flat_a))
    flat_b = flat_b + [0] * (n - len(flat_b))
    dot = sum(x * y for x, y in zip(flat_a, flat_b))
    norm_a = math.sqrt(sum(x * x for x in flat_a))
    norm_b = math.sqrt(sum(y * y for y in flat_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _flatten(rows: tuple) -> list[int]:
    """Flatten a tuple of dtype-count tuples into a 1-D list."""
    out: list[int] = []
    for row in rows:
        out.extend(row)
    return out
