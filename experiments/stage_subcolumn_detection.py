"""Strategies for sub-problem #5: detect stage sub-column labels.

Given a sheet and a candidate stage-name row, return a set of
(col_letter, sub_label_raw) pairs that the strategy claims are sub-columns.

We expose three strategies:

- single_row:   read the row directly below the stage-name row
- multi_row:    probe N+1 and N+2; prefer the row with more sub-field vocab hits
- inferred:     scan rows 1..6 for ANY cell matching sub-field vocab, take all

Ground truth comes from corpus.subcol_cases — the best sub_label_row and the
expected (col, raw) pairs.
"""
from __future__ import annotations

import re
from typing import Callable

from openpyxl.utils import get_column_letter

from field_matcher_strategies import SUBFIELD_VOCAB, _norm


_SUBFIELD_ALIASES = {_norm(s) for aliases in SUBFIELD_VOCAB.values() for s in aliases} \
    | {_norm(k.replace("_", " ")) for k in SUBFIELD_VOCAB}


def _is_subfield(v: object) -> bool:
    if not isinstance(v, str):
        return False
    n = _norm(v)
    return bool(n) and n in _SUBFIELD_ALIASES


def _harvest_row(ws, row: int, max_col: int) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for c in range(1, max_col + 1):
        v = ws.cell(row=row, column=c).value
        if _is_subfield(v):
            out.add((get_column_letter(c), v.strip()))
    return out


def single_row(ws, max_row: int, max_col: int, stage_name_row: int) -> set[tuple[str, str]]:
    """Read sub-labels from the row directly below the stage-name row."""
    target = stage_name_row + 1
    if target > max_row:
        return set()
    return _harvest_row(ws, target, max_col)


def multi_row(
    ws, max_row: int, max_col: int, stage_name_row: int,
) -> set[tuple[str, str]]:
    """Probe N+1 and N+2; return the row with more sub-field vocab hits.

    Ties broken in favour of N+1.
    """
    r1 = _harvest_row(ws, stage_name_row + 1, max_col) if stage_name_row + 1 <= max_row else set()
    r2 = _harvest_row(ws, stage_name_row + 2, max_col) if stage_name_row + 2 <= max_row else set()
    return r1 if len(r1) >= len(r2) else r2


def inferred(
    ws, max_row: int, max_col: int, stage_name_row: int,
) -> set[tuple[str, str]]:
    """Pick the row in 1..6 with the highest sub-field vocab count, union it."""
    best_row: int | None = None
    best_count = 0
    probe_end = min(max_row, 6)
    for r in range(1, probe_end + 1):
        cnt = sum(
            1 for c in range(1, max_col + 1)
            if _is_subfield(ws.cell(row=r, column=c).value)
        )
        if cnt > best_count:
            best_count = cnt
            best_row = r
    if best_row is None:
        return set()
    return _harvest_row(ws, best_row, max_col)


STRATEGIES: dict[str, Callable[..., set[tuple[str, str]]]] = {
    "single_row": single_row,
    "multi_row": multi_row,
    "inferred": inferred,
}
