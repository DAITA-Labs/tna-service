"""find_field_locations — the parametric workhorse.

Called once per FieldSpec. Scans the sheet for candidate label cells, scores
them against the spec's aliases (vocab / fuzzy / jaccard, gated by
spec.label_match_mode), finds adjacent value cells, scores those against the
spec's value_dtype + value_constraints, and emits DetectedFieldLocation
records.

Three label-strategy variants:
    A — vocab_only         (alias exact match)
    B — vocab_plus_fuzzy   (vocab first; fuzzy >= 90 fallback)
    C — combined_weighted  (vocab + fuzzy + token-jaccard, gated by spec.label_match_mode)

Two dtype-enforcement variants:
    A — strict — reject when spec.value_dtype_mode == HARD and dtype mismatches
    B — soft   — never reject; dtype is only a score modifier
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any

from openpyxl.utils.cell import get_column_letter

from experiments.specs._base import FieldSpec
from experiments.specs.enums import LabelMatchMode, ValueDtype, ValueDtypeMode, ValuePattern
from experiments.specs.identifiers import IDENTIFIER_SPECS
from experiments.specs.metadata import METADATA_SPECS
from experiments.specs.stages import STAGE_SPECS

from experiments.p1.shape_models import Rect, ShapeSummary
from experiments.p1.shape_tools import _looks_like_date_string  # private but stable

from .locator_models import DetectedFieldLocation


# Pre-compute the cross-spec alias set so we can identify "this cell is itself
# a label" — used to reject pathological KV candidates where the value cell
# is just another header (e.g. M3="Col" + N3="Qty" both being sub-headers).
_ALL_LABEL_ALIASES: set[str] = set()
for _registry in (IDENTIFIER_SPECS, METADATA_SPECS, STAGE_SPECS):
    for _spec in _registry:
        _ALL_LABEL_ALIASES.add(re.sub(r"\s+", " ", _spec.canonical).strip().lower())
        for _a in _spec.aliases:
            _ALL_LABEL_ALIASES.add(re.sub(r"\s+", " ", _a).strip().lower())


# =============================================================================
# Text / dtype helpers
# =============================================================================


def _a1(row: int, col: int) -> str:
    return f"{get_column_letter(col)}{row}"


def _norm_label(s: Any) -> str:
    """Normalise a label for vocab matching: lower-case, collapse whitespace,
    strip trailing punctuation like ':' '.' '#' (but keep '#' inside)."""
    if not isinstance(s, str):
        return ""
    out = re.sub(r"\s+", " ", s).strip().lower()
    # Strip trailing punctuation often appended to labels in TNAs
    while out and out[-1] in ":.,;":
        out = out[:-1].strip()
    return out


def _tokenise(s: str) -> set[str]:
    return {t for t in re.split(r"[\s\W_]+", s.lower()) if t}


def _dtype_of(value: Any) -> str:
    """Coarse dtype label aligned with FieldSpec.value_dtype."""
    if value is None:
        return "blank"
    if isinstance(value, (_dt.date, _dt.datetime)):
        return "date"
    if isinstance(value, bool):
        return "str"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value != value:  # NaN
            return "blank"
        return "int"
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return "blank"
        if _looks_like_date_string(s):
            return "date"
        return "str"
    return "str"


def _classify_pattern(value: Any, observed_dtype: str) -> ValuePattern:
    """Map a single cell's value to one of the ValuePattern enums."""
    if observed_dtype == "date":
        return ValuePattern.DATE
    if observed_dtype == "int":
        try:
            iv = float(value)
        except Exception:
            return ValuePattern.MIXED
        if -10 <= iv <= 10:
            return ValuePattern.INT_SMALL
        if iv < 1000:
            return ValuePattern.INT_MEDIUM
        return ValuePattern.INT_LARGE
    if observed_dtype == "blank":
        return ValuePattern.BLANK
    s = str(value).strip()
    has_alpha = any(ch.isalpha() for ch in s)
    has_digit = any(ch.isdigit() for ch in s)
    # Pure-digit strings (e.g. '6602', '131673') — treat as INT_MEDIUM /
    # INT_LARGE by their numeric magnitude. Openpyxl sometimes hands these
    # back as str when the cell format is text.
    if has_digit and not has_alpha:
        try:
            iv = int(s.replace(",", "").replace(" ", ""))
            if -10 <= iv <= 10:
                return ValuePattern.INT_SMALL
            if iv < 1000:
                return ValuePattern.INT_MEDIUM
            return ValuePattern.INT_LARGE
        except ValueError:
            pass
    if has_alpha and has_digit and len(s) <= 15:
        return ValuePattern.CODE_ALNUM
    if len(s) <= 4 and not has_digit:
        return ValuePattern.CODE_ALNUM
    return ValuePattern.NAME_TEXT


# =============================================================================
# Label scoring — three variants
# =============================================================================


def _label_match_vocab_only(text: str, aliases: list[str]) -> tuple[float, str]:
    if not text:
        return 0.0, ""
    if text in aliases:
        return 1.0, "vocab"
    return 0.0, ""


def _label_match_vocab_plus_fuzzy(text: str, aliases: list[str]) -> tuple[float, str]:
    if not text:
        return 0.0, ""
    if text in aliases:
        return 1.0, "vocab"
    try:
        from rapidfuzz import fuzz
    except Exception:
        return 0.0, ""
    best = 0.0
    for a in aliases:
        if not a:
            continue
        r = fuzz.ratio(text, a) / 100.0
        if r > best:
            best = r
    if best >= 0.90:
        return best, "fuzzy"
    return 0.0, ""


def _label_match_combined(
    text: str, aliases: list[str], mode: LabelMatchMode,
) -> tuple[float, str]:
    """Variant C — respects spec.label_match_mode.

    HARD   = vocab only
    MEDIUM = vocab OR fuzzy >= 0.90 OR jaccard >= 0.7
    SOFT   = MEDIUM OR fuzzy >= 0.70 OR jaccard >= 0.5
    """
    if not text:
        return 0.0, ""
    if text in aliases:
        return 1.0, "vocab"
    if mode == LabelMatchMode.HARD:
        return 0.0, ""

    fuzzy_score = 0.0
    try:
        from rapidfuzz import fuzz
        for a in aliases:
            if not a:
                continue
            r = fuzz.ratio(text, a) / 100.0
            if r > fuzzy_score:
                fuzzy_score = r
    except Exception:
        pass

    # token-jaccard
    text_toks = _tokenise(text)
    jaccard_score = 0.0
    for a in aliases:
        a_toks = _tokenise(a)
        if not a_toks or not text_toks:
            continue
        inter = len(text_toks & a_toks)
        uni = len(text_toks | a_toks)
        j = inter / uni if uni else 0.0
        if j > jaccard_score:
            jaccard_score = j

    # Apply mode thresholds
    if mode == LabelMatchMode.MEDIUM:
        if fuzzy_score >= 0.90:
            return 0.7 * fuzzy_score, "fuzzy"
        if jaccard_score >= 0.7:
            return 0.5 * jaccard_score, "jaccard"
        return 0.0, ""

    # SOFT
    if fuzzy_score >= 0.90:
        return 0.7 * fuzzy_score, "fuzzy"
    if jaccard_score >= 0.7:
        return 0.5 * jaccard_score, "jaccard"
    if fuzzy_score >= 0.70:
        return 0.5 * fuzzy_score, "fuzzy_soft"
    if jaccard_score >= 0.5:
        return 0.4 * jaccard_score, "jaccard_soft"
    return 0.0, ""


def score_label(
    text: str, spec: FieldSpec, strategy: str = "combined_weighted",
) -> tuple[float, str]:
    """Public entrypoint: score a candidate label text against a spec."""
    norm = _norm_label(text)
    if not norm:
        return 0.0, ""
    aliases = [_norm_label(a) for a in spec.aliases]
    # Anti-pattern check — short-circuit if the text matches an anti-canonical
    # alias (the spec's anti_patterns mention them, but we also need to filter
    # by other specs' aliases to prevent cross-matching). We do that at the
    # extractor level (reconciliation) rather than here.
    if strategy == "vocab_only":
        return _label_match_vocab_only(norm, aliases)
    if strategy == "vocab_plus_fuzzy":
        return _label_match_vocab_plus_fuzzy(norm, aliases)
    # combined_weighted
    return _label_match_combined(norm, aliases, spec.label_match_mode)


# =============================================================================
# Value scoring
# =============================================================================


def score_value(
    value: Any, observed_dtype: str, spec: FieldSpec, dtype_strategy: str = "strict",
) -> float:
    """Score how well a value fits the spec's value_dtype + constraints.

    Returns a value in [0, 1]. 0 means "definite mismatch" only when dtype is
    HARD and strict is enabled. Otherwise scores degrade gracefully.
    """
    if observed_dtype == "blank":
        return 0.0

    score = 1.0

    # Dtype match
    want = spec.value_dtype
    if want == ValueDtype.ANY:
        dtype_ok = True
    elif want == ValueDtype.INT:
        dtype_ok = observed_dtype == "int"
    elif want == ValueDtype.DATE:
        dtype_ok = observed_dtype == "date"
    elif want == ValueDtype.STR:
        # accept str AND int (a numeric color_code might look like an int)
        dtype_ok = observed_dtype in ("str", "int")
    else:
        dtype_ok = True

    if not dtype_ok:
        if spec.value_dtype_mode == ValueDtypeMode.HARD:
            if dtype_strategy == "strict":
                return 0.0
            else:
                score *= 0.3
        elif spec.value_dtype_mode == ValueDtypeMode.MEDIUM:
            score *= 0.5
        else:  # SOFT
            score *= 0.9

    # Range / length / pattern constraints
    cons = spec.value_constraints
    if cons.min is not None or cons.max is not None:
        try:
            v_num = float(value)
            if cons.min is not None and v_num < cons.min:
                if spec.value_dtype_mode == ValueDtypeMode.HARD and dtype_strategy == "strict":
                    return 0.0
                score *= 0.5
            if cons.max is not None and v_num > cons.max:
                if spec.value_dtype_mode == ValueDtypeMode.HARD and dtype_strategy == "strict":
                    return 0.0
                score *= 0.5
        except (TypeError, ValueError):
            pass

    if cons.min_len is not None or cons.max_len is not None:
        s_len = len(str(value).strip()) if value is not None else 0
        if cons.min_len is not None and s_len < cons.min_len:
            score *= 0.6
        if cons.max_len is not None and s_len > cons.max_len:
            # Length over-shoot is a strong signal of mis-categorisation
            # (e.g. a long fabric_name being matched against fabric_code).
            if spec.value_dtype_mode == ValueDtypeMode.HARD and dtype_strategy == "strict":
                return 0.0
            score *= 0.3

    # Pattern match
    if cons.allowed_patterns:
        observed_pattern = _classify_pattern(value, observed_dtype)
        if observed_pattern not in cons.allowed_patterns:
            # Soften — pattern is informational; constraint-violation
            # is only fatal when both dtype_mode=HARD and dtype mismatch.
            if observed_pattern == ValuePattern.NAME_TEXT and (
                ValuePattern.CODE_ALNUM in cons.allowed_patterns
                or ValuePattern.INT_LARGE in cons.allowed_patterns
            ):
                # Probably a long descriptive value where a code was expected
                score *= 0.3
            else:
                score *= 0.6

    return max(0.0, min(1.0, score))


# =============================================================================
# Candidate generation — sheet scan
# =============================================================================


def _is_label_like(value: Any) -> bool:
    """True if a cell value could plausibly be a label (short text)."""
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not s or len(s) > 40:
        return False
    return True


def _adjacent_value_cells(
    grid: list[list], label_row: int, label_col: int,
) -> list[tuple[int, int, Any]]:
    """Cells to consider as the value for a label at (label_row, label_col).

    Returns up to 4 candidates: right (same row), below (same col), 2-right
    (some KV layouts skip a column), 2-below.
    """
    out: list[tuple[int, int, Any]] = []
    rows = len(grid)
    cols = max((len(r) for r in grid), default=0)

    candidates = [
        (label_row, label_col + 1),
        (label_row, label_col + 2),
        (label_row + 1, label_col),
        (label_row + 2, label_col),
    ]
    for r, c in candidates:
        if 1 <= r <= rows and 1 <= c <= cols:
            row = grid[r - 1]
            if c - 1 < len(row):
                v = row[c - 1].value
                if v is not None and not (isinstance(v, str) and v.strip() == ""):
                    out.append((r, c, v))
    return out


def _read_column_values(
    grid: list[list], header_row: int, col: int, max_row: int,
) -> tuple[list[Any], list[int]]:
    """Read the values directly below a column header. Returns (values, rows).

    Reads every row from `header_row + 1` to `max_row` (inclusive) and
    *includes blank rows* for callers who need to count PLI anchors. The
    caller can post-filter for non-blank-only counts. We DO trim the trailing
    blank tail (i.e. blanks past the last value).
    """
    values: list[Any] = []
    rows: list[int] = []
    last_value_idx = -1
    for r in range(header_row + 1, max_row + 1):
        row = grid[r - 1]
        if col - 1 < len(row):
            v = row[col - 1].value
        else:
            v = None
        is_blank = v is None or (isinstance(v, str) and v.strip() == "")
        # Skip a "Grand Total" row by heuristic: cell in col 1 says 'Grand Total'
        if 0 < len(row):
            c1 = row[0].value if 0 < len(row) else None
            if isinstance(c1, str) and "total" in c1.lower() and len(c1) <= 15:
                continue
        values.append(None if is_blank else v)
        rows.append(r)
        if not is_blank:
            last_value_idx = len(values) - 1
    # Trim trailing blanks
    if last_value_idx >= 0:
        values = values[: last_value_idx + 1]
        rows = rows[: last_value_idx + 1]
    return values, rows


# =============================================================================
# Main entrypoint
# =============================================================================


def find_field_locations(
    grid: list[list],
    shape: ShapeSummary,
    spec: FieldSpec,
    *,
    label_strategy: str = "combined_weighted",
    dtype_strategy: str = "strict",
    label_score_threshold: float | None = None,
    value_score_threshold: float = 0.05,
) -> list[DetectedFieldLocation]:
    """Scan the sheet for candidate cells matching `spec`.

    Returns a ranked, deduped list. Each candidate carries a label_score, a
    value_score, and a kind ("kv" | "kv_vertical" | "column_header").
    """
    candidates: list[DetectedFieldLocation] = []

    # Discover header rows for the column-header search path.
    #
    # In 2-row header stacks (DKN row 2 + row 3, CB row 2 + row 3) we want
    # BOTH rows callable as header anchors — but the data starts BELOW the
    # lower of the two. The trick: header_rows is the union of (a) the
    # P1-chosen best_header_row, plus (b) any other vocab-scored row within
    # 2 rows of it that scored >= 5. data_start_row = max(header_rows) + 1
    # so the column-header path skips any sub-header row when reading values.
    biggest: Rect | None = shape.biggest_rect
    primary_header_row = shape.best_header_row
    header_rows: set[int] = set()
    if primary_header_row is not None:
        header_rows.add(primary_header_row)
        for hc in shape.header_candidates:
            if (hc.signal == "vocab" and hc.score >= 5
                    and abs(hc.row - primary_header_row) <= 2):
                header_rows.add(hc.row)

    # Data values start below the lowest header row.
    data_start_row = (max(header_rows) + 1) if header_rows else (
        (biggest.r0 + 1) if biggest else 2
    )

    # Skip any further sub-header row(s): rows where >50% of non-blank cells
    # are short text tokens (likely PLAN/ACT/QTY/COL sub-labels). MOPD has
    # this shape at row 3 even though row 3's vocab score doesn't qualify it
    # as a header row on its own.
    if biggest is not None:
        while data_start_row <= biggest.r1:
            row = grid[data_start_row - 1]
            non_blank = 0
            short_text = 0
            for cell in row:
                v = cell.value
                if v is None or (isinstance(v, str) and v.strip() == ""):
                    continue
                non_blank += 1
                if isinstance(v, str) and len(v.strip()) <= 8:
                    short_text += 1
            if non_blank >= 3 and short_text / non_blank > 0.5:
                data_start_row += 1
                continue
            break

    # Threshold: spec's label_match_mode drives the minimum score we accept
    if label_score_threshold is None:
        if spec.label_match_mode == LabelMatchMode.HARD:
            label_score_threshold = 0.99
        elif spec.label_match_mode == LabelMatchMode.MEDIUM:
            label_score_threshold = 0.45
        else:
            label_score_threshold = 0.30

    rows = len(grid)
    cols = max((len(r) for r in grid), default=0)

    for r in range(1, rows + 1):
        row = grid[r - 1]
        for c in range(1, min(len(row), cols) + 1):
            cell = row[c - 1]
            v = cell.value
            if not _is_label_like(v):
                continue
            label_score, label_signal = score_label(v, spec, label_strategy)
            if label_score < label_score_threshold:
                continue
            label_text = _norm_label(v)

            # -- Column-header path: only if (r in header_rows) AND there are
            #    data rows below this column.
            if r in header_rows and biggest is not None and r <= biggest.r1:
                # Read values from the *data start* row (skipping any
                # sub-header rows between this header and the data).
                read_from = max(r, data_start_row - 1)
                # Top-row bonus: a label at the topmost header row is more
                # trustworthy than a label at a sub-header. This is the
                # ROW_PER_PLI convention — the main header is the topmost.
                topmost_header = min(header_rows) if header_rows else r
                top_row_bonus = 0.15 if r == topmost_header else 0.0
                col_vals, col_rows = _read_column_values(
                    grid, header_row=read_from, col=c, max_row=biggest.r1,
                )
                # avoid emitting a column-header candidate with zero values
                if col_vals:
                    # Per-value scoring — average over non-blank values; if
                    # HARD-dtype and strict and >50% mismatch (among non-blank),
                    # drop the candidate.
                    val_scores = []
                    non_blank_scores = []
                    for vv in col_vals:
                        if vv is None or (isinstance(vv, str) and vv.strip() == ""):
                            val_scores.append(0.0)
                            continue
                        dt = _dtype_of(vv)
                        s = score_value(vv, dt, spec, dtype_strategy)
                        val_scores.append(s)
                        non_blank_scores.append(s)
                    avg_val_score = (
                        sum(non_blank_scores) / len(non_blank_scores)
                        if non_blank_scores else 0.0
                    )
                    n_zero = sum(1 for s in non_blank_scores if s == 0)
                    if not (
                        dtype_strategy == "strict"
                        and spec.value_dtype_mode == ValueDtypeMode.HARD
                        and non_blank_scores
                        and n_zero > len(non_blank_scores) // 2
                    ):
                        first_nonblank = next(
                            (v for v in col_vals if v is not None
                             and not (isinstance(v, str) and v.strip() == "")),
                            None,
                        )
                        first_dt = _dtype_of(first_nonblank)
                        combined = (
                            0.7 * label_score + 0.3 * avg_val_score + top_row_bonus
                        )
                        combined = min(combined, 1.0)
                        candidates.append(DetectedFieldLocation(
                            canonical=spec.canonical,
                            kind="column_header",
                            label_cell=_a1(r, c),
                            label_text=label_text,
                            label_row=r,
                            label_col=c,
                            value_cell=_a1(r, c),
                            value_row=r,
                            value_col=c,
                            value=first_nonblank,
                            observed_dtype=first_dt,
                            label_score=label_score,
                            value_score=avg_val_score,
                            combined_score=combined,
                            label_signal=label_signal,
                            column_values=col_vals,
                            column_value_rows=col_rows,
                            evidence=[
                                f"column-header at {_a1(r, c)} with {len(col_vals)} data values",
                                f"label_signal={label_signal} score={label_score:.2f}",
                                f"avg_value_score={avg_val_score:.2f}",
                                f"top_row_bonus={top_row_bonus:.2f}",
                            ],
                        ))
                    # don't also emit a kv candidate for the same cell — the
                    # column scan dominates if the value is below.
                    continue

            # -- KV path: probe right + below.
            #
            # If we're on a known header row, the cells immediately to the
            # right are themselves column headers — NOT values. Restrict the
            # KV path to non-header rows. (A KV layout normally has labels
            # off the data rectangle entirely, in a metadata strip.)
            on_header_row = (
                r in header_rows
                or (primary_header_row is not None
                    and abs(r - primary_header_row) <= 1)
            )
            adj = _adjacent_value_cells(grid, r, c)
            for vr, vc, vv in adj:
                # When the label sits on a header row, ONLY allow vertical
                # value pickups (kv_vertical) — the right-neighbour is
                # always another header. This is critical for CB's row 2
                # where every cell is a header.
                if on_header_row and vr == r:
                    continue
                dt = _dtype_of(vv)
                val_score = score_value(vv, dt, spec, dtype_strategy)
                if val_score < value_score_threshold:
                    continue
                # Reject when the value cell is itself a known label/alias —
                # this prevents M3="Col" + N3="Qty" style sub-header pairs
                # from polluting the candidate list.
                if isinstance(vv, str):
                    vv_norm = _norm_label(vv)
                    if vv_norm and vv_norm in _ALL_LABEL_ALIASES:
                        continue
                kind = "kv" if vr == r else "kv_vertical"
                candidates.append(DetectedFieldLocation(
                    canonical=spec.canonical,
                    kind=kind,
                    label_cell=_a1(r, c),
                    label_text=label_text,
                    label_row=r,
                    label_col=c,
                    value_cell=_a1(vr, vc),
                    value_row=vr,
                    value_col=vc,
                    value=vv,
                    observed_dtype=dt,
                    label_score=label_score,
                    value_score=val_score,
                    combined_score=0.7 * label_score + 0.3 * val_score,
                    label_signal=label_signal,
                    evidence=[
                        f"label at {_a1(r, c)} ({label_signal}, score={label_score:.2f})",
                        f"value at {_a1(vr, vc)} dtype={dt} score={val_score:.2f}",
                    ],
                ))
                # Take the highest-scoring adjacent value — break after the
                # first that scored above threshold. Keep the right-hand
                # neighbour as the primary KV candidate.
                break

    # Dedupe: same canonical + same (label_cell, value_cell) — keep highest combined
    seen: dict[tuple[str, str, str], DetectedFieldLocation] = {}
    for cand in candidates:
        key = (cand.canonical, cand.label_cell, cand.value_cell or "")
        if key not in seen or cand.combined_score > seen[key].combined_score:
            seen[key] = cand
    deduped = list(seen.values())
    deduped.sort(key=lambda x: x.combined_score, reverse=True)
    return deduped
