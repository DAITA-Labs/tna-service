"""Strategies for sub-problem #4: detect stage-band rectangles.

Each strategy takes a sheet's cell grid (openpyxl ws or 2D list) and returns
a set of column indices it claims are 'stage data columns'. The harness
compares those against the corpus-derived expected column set per file.

We expose three strategies:

- date_density:  any column whose first 6 non-header rows are ≥30% dates
- vocab_row:     scan rows 1..5 for known stage vocab; column-of-hit is a band
- hybrid:        vocab_row union date_density (fallback when vocab is empty)

Output is a set of column-letter strings (e.g. {'R', 'T', 'V'}); the score
is set-similarity (precision, recall, F1) against the expected set.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Callable

from openpyxl.utils import get_column_letter

from field_matcher_strategies import STAGE_VOCAB, _norm


_DATE_RE = re.compile(
    r"^\s*(?:"
    r"\d{1,2}[-/]\w{3}[-/]\d{2,4}|"
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|"
    r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
    r")\s*$",
    re.IGNORECASE,
)


def _is_date(v: object) -> bool:
    if isinstance(v, (date, datetime)):
        return True
    if isinstance(v, str):
        return bool(_DATE_RE.match(v))
    return False


def _flatten_vocab() -> set[str]:
    return {_norm(s) for aliases in STAGE_VOCAB.values() for s in aliases} \
        | {_norm(k.replace("_", " ")) for k in STAGE_VOCAB}


_STAGE_VOCAB_SET = _flatten_vocab()


# === Strategy A: date-density ================================================

def date_density(
    ws, max_row: int, max_col: int, header_rows: int = 3,
    min_ratio: float = 0.3, min_dates: int = 2,
) -> set[str]:
    """Mark columns where ≥min_ratio of data-row cells are dates.

    Skip the first `header_rows` rows. Sample up to 20 rows below.
    """
    cols: set[str] = set()
    start = header_rows + 1
    end = min(max_row, header_rows + 20)
    if end < start:
        return cols
    for c in range(1, max_col + 1):
        date_count = 0
        non_empty = 0
        for r in range(start, end + 1):
            v = ws.cell(row=r, column=c).value
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            non_empty += 1
            if _is_date(v):
                date_count += 1
        if non_empty == 0:
            continue
        if date_count >= min_dates and (date_count / non_empty) >= min_ratio:
            cols.add(get_column_letter(c))
    return cols


# === Strategy B: vocab-row ===================================================

def vocab_row(
    ws, max_row: int, max_col: int, probe_rows: int = 3,
) -> set[str]:
    """Mark columns whose header cell (rows 1..probe_rows) matches stage vocab.

    Probes only 3 rows by default — going deeper picks up vocab leakage from
    data rows (e.g. cells containing 'Fabric' in product descriptions).
    """
    cols: set[str] = set()
    last_row = min(probe_rows, max_row)
    for r in range(1, last_row + 1):
        for c in range(1, max_col + 1):
            v = ws.cell(row=r, column=c).value
            if not isinstance(v, str):
                continue
            n = _norm(v)
            if not n:
                continue
            # exact alias match (whole cell)
            if n in _STAGE_VOCAB_SET:
                cols.add(get_column_letter(c))
                continue
            # substring match restricted to alias tokens of length ≥5 to avoid
            # 'fi', 'pp', 'fab' false positives. Also require the cell to be
            # short-ish (≤30 chars) — long strings are descriptions, not headers.
            if len(n) > 30:
                continue
            for alias in _STAGE_VOCAB_SET:
                if len(alias) >= 5 and alias in n:
                    cols.add(get_column_letter(c))
                    break
    return cols


# === Strategy C: hybrid ======================================================

def hybrid(
    ws, max_row: int, max_col: int,
) -> set[str]:
    """Vocab first; union date-density when vocab finds <3 columns."""
    voc = vocab_row(ws, max_row, max_col)
    if len(voc) >= 3:
        return voc
    return voc | date_density(ws, max_row, max_col)


STRATEGIES: dict[str, Callable[..., set[str]]] = {
    "date_density": date_density,
    "vocab_row": vocab_row,
    "hybrid": hybrid,
}
