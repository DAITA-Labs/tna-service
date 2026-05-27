"""Score extracted identifiers against the dataset label JSON.

Computes:
  - Expected scope per canonical (from label values across PLIs)
  - Scope-prediction accuracy
  - Per-field value precision/recall
  - Per-PLI value match samples
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from openpyxl.utils.cell import column_index_from_string, coordinate_from_string

from experiments.specs.enums import FieldScope, ReadDirection

from .locator_models import (
    DetectedFieldLocation,
    FieldLocator,
    IdentifierExtractionResult,
    ScopeDecision,
)


# Canonical reconciliation between spec names and label-file names.
# In our 6 files the label-file already uses the spec canonical names.
LABEL_KEY_MAP = {
    # spec_canonical: [label_key candidates in priority order]
    "io_number": ["io_number"],
    "quantity": ["quantity", "order_quantity"],
    "style_code": ["style_code"],
    "style_name": ["style_name"],
    "color_code": ["color_code", "color"],
    "color_name": ["color_name"],
    "fabric_code": ["fabric_code", "fabric"],
    "fabric_name": ["fabric_name"],
    "delivery_date": ["delivery_date"],
}


def _label_value_for(pli: dict, canonical: str) -> Any:
    for key in LABEL_KEY_MAP.get(canonical, [canonical]):
        if key in pli and pli[key] not in ("", None):
            return pli[key]
    return None


def infer_expected_scope(values: list[Any]) -> FieldScope:
    """From the per-PLI value vector, infer the SHEET/GROUP/PLI scope."""
    non_null = [v for v in values if v not in (None, "")]
    if not non_null:
        return FieldScope.PLI
    distinct = set(_canon_value(v) for v in non_null)
    if len(distinct) == 1 and len(non_null) == len(values):
        return FieldScope.SHEET
    if len(distinct) == 1:
        # all-non-null values agree but some PLIs lack data — still SHEET
        return FieldScope.SHEET
    # contiguous-block check — count runs of equal-valued consecutive values
    if len(distinct) < len(non_null):
        # Walk the values; count runs
        runs = 0
        prev = object()
        for v in values:
            cv = _canon_value(v) if v not in (None, "") else None
            if cv != prev:
                runs += 1
                prev = cv
        if runs <= len(distinct) + 1:
            return FieldScope.GROUP
    return FieldScope.PLI


def _canon_value(v: Any) -> str:
    if isinstance(v, (_dt.date, _dt.datetime)):
        return v.isoformat()[:10]
    return re.sub(r"\s+", " ", str(v)).strip().lower()


def _values_match(expected: Any, observed: Any) -> bool:
    if expected is None and observed is None:
        return True
    if expected is None or observed is None:
        return False
    return _canon_value(expected) == _canon_value(observed)


# =============================================================================
# Read a value from the sheet via a FieldLocator + pli anchor
# =============================================================================


def _coord_to_rc(a1: str) -> tuple[int, int]:
    col_str, row = coordinate_from_string(a1)
    return row, column_index_from_string(col_str)


def read_value(
    grid: list[list], locator: FieldLocator, pli_anchor_row: int | None,
) -> Any:
    """Resolve a FieldLocator to a cell value, given a PLI anchor row.

    For FIXED locators, pli_anchor_row is ignored.
    For SAME_ROW locators, we read (pli_anchor_row, anchor_col).
    """
    rp = locator.read_pattern
    if rp is None:
        return None
    if rp.direction == ReadDirection.FIXED and rp.fixed_cell:
        r, c = _coord_to_rc(rp.fixed_cell)
    elif rp.direction == ReadDirection.SAME_ROW and rp.anchor_col and pli_anchor_row:
        r = pli_anchor_row
        c = column_index_from_string(rp.anchor_col)
    else:
        return None
    if 1 <= r <= len(grid):
        row = grid[r - 1]
        if 1 <= c <= len(row):
            return row[c - 1].value
    return None


# =============================================================================
# Per-file scoring
# =============================================================================


def _flatten_pli_rows(pli: dict) -> list[int]:
    """Get the PLI's anchor rows. Use first if multiple."""
    rs = pli.get("source_rows") or []
    return rs


def score_file(
    result: IdentifierExtractionResult,
    label_path: Path,
    grid: list[list],
) -> dict:
    """Compare extraction result vs labels file."""
    if not label_path.exists():
        return {"error": f"label not found: {label_path}"}
    labels = json.loads(label_path.read_text())
    plis = labels.get("plis", [])
    n_label_plis = len(plis)

    # Build per-canonical expected vectors. Restrict to PLIs belonging to the
    # sheet the extractor analysed — otherwise multi-sheet workbooks
    # (Eastman) inflate the PLI count and confuse scope inference.
    plis_in_sheet = [
        p for p in plis if p.get("source_sheet") == result.sheet_name
    ]
    plis_for_scope = plis_in_sheet if plis_in_sheet else plis

    expected_vectors: dict[str, list[Any]] = {}
    for canonical in LABEL_KEY_MAP:
        expected_vectors[canonical] = [
            _label_value_for(pli, canonical) for pli in plis_for_scope
        ]

    expected_scope: dict[str, FieldScope] = {
        c: infer_expected_scope(vs) for c, vs in expected_vectors.items()
    }

    # PLI anchor rows for the *current sheet only*.
    sheet_anchor_rows: list[int] = []
    for pli in plis:
        if pli.get("source_sheet") != result.sheet_name:
            continue
        rs = _flatten_pli_rows(pli)
        if rs:
            sheet_anchor_rows.append(rs[0])
    sheet_anchor_rows = sorted(set(sheet_anchor_rows))

    # Per-canonical scoring
    per_canonical: dict[str, dict] = {}
    for canonical in LABEL_KEY_MAP:
        observed_locator = result.field_locators.get(canonical)
        observed_scope = result.scope_decisions.get(canonical)
        exp_scope = expected_scope[canonical]
        exp_values = expected_vectors[canonical]
        has_any_label = any(v not in (None, "") for v in exp_values)

        row = {
            "canonical": canonical,
            "expected_scope": exp_scope.value if has_any_label else "absent",
            "predicted_scope": observed_scope.scope.value if observed_scope else "none",
            "scope_correct": False,
            "has_locator": observed_locator is not None,
            "has_label": has_any_label,
            "matches": 0,
            "predictions": 0,
            "label_present": sum(1 for v in exp_values if v not in (None, "")),
            "samples": [],
            "chosen_cell": observed_locator.read_pattern.fixed_cell if observed_locator and observed_locator.read_pattern and observed_locator.read_pattern.fixed_cell else None,
            "chosen_anchor_col": observed_locator.read_pattern.anchor_col if observed_locator and observed_locator.read_pattern and observed_locator.read_pattern.anchor_col else None,
            "confidence": observed_locator.confidence if observed_locator else 0.0,
        }

        if not has_any_label:
            per_canonical[canonical] = row
            continue

        if observed_locator is None:
            per_canonical[canonical] = row
            continue

        # scope correctness — exact-match OR "compatible" (PLI-anchored
        # locator that reads the same value across every PLI is functionally
        # equivalent to a SHEET-scoped one — both extract the same data).
        if observed_scope is not None:
            if observed_scope.scope == exp_scope:
                row["scope_correct"] = True
            elif (exp_scope == FieldScope.SHEET
                    and observed_scope.scope == FieldScope.PLI):
                row["scope_correct"] = True
                row["scope_correct_compatible"] = True
            elif (exp_scope == FieldScope.GROUP
                    and observed_scope.scope == FieldScope.PLI):
                # PLI subsumes GROUP for apply_plan purposes (each PLI reads
                # its own row even when values repeat).
                row["scope_correct"] = True
                row["scope_correct_compatible"] = True

        # value match: walk PLIs in label order; for SHEET, read once
        if observed_locator.scope == FieldScope.SHEET:
            obs = read_value(grid, observed_locator, None)
            for pli, exp in zip(plis_for_scope, exp_values):
                if exp in (None, ""):
                    continue
                if _values_match(exp, obs):
                    row["matches"] += 1
                row["samples"].append({
                    "expected": exp, "observed": obs,
                    "match": _values_match(exp, obs),
                })
                if len(row["samples"]) >= 3:
                    break
            row["predictions"] = sum(1 for s in row["samples"]) or 1
        elif observed_locator.scope == FieldScope.PLI:
            preds = 0
            matches = 0
            samples = []
            for pli, exp in zip(plis_for_scope, exp_values):
                rs = _flatten_pli_rows(pli)
                anchor = rs[0] if rs else None
                obs = read_value(grid, observed_locator, anchor)
                if obs not in (None, ""):
                    preds += 1
                if _values_match(exp, obs):
                    matches += 1
                if len(samples) < 3:
                    samples.append({
                        "anchor_row": anchor,
                        "expected": exp, "observed": obs,
                        "match": _values_match(exp, obs),
                    })
            row["predictions"] = preds
            row["matches"] = matches
            row["samples"] = samples
        else:  # GROUP
            row["predictions"] = 0
            row["samples"] = [{"note": "GROUP scope not directly read; would need PliGroup resolution"}]

        per_canonical[canonical] = row

    # Aggregate per-file
    n_scope_correct = sum(
        1 for c in per_canonical.values()
        if c["has_label"] and c["scope_correct"]
    )
    n_with_label = sum(1 for c in per_canonical.values() if c["has_label"])
    n_predicted = sum(c["predictions"] for c in per_canonical.values())
    n_matched = sum(c["matches"] for c in per_canonical.values())

    # End-to-end PLI count we could produce (rough): use any PLI-scoped
    # column-anchored locator (io_number preferred; fall through to
    # style_code / quantity).
    e2e_plis = 0
    for cand_canonical in ("io_number", "style_code", "quantity",
                            "style_name", "color_name"):
        loc = result.field_locators.get(cand_canonical)
        if not loc:
            continue
        if loc.scope == FieldScope.PLI and loc.read_pattern and loc.read_pattern.anchor_col:
            c = column_index_from_string(loc.read_pattern.anchor_col)
            e2e_plis = _count_anchor_col_values(grid, c)
            break
        if loc.scope == FieldScope.SHEET:
            e2e_plis = 1  # SHEET_IS_PLI
            break

    return {
        "file": result.file,
        "sheet_name": result.sheet_name,
        "n_label_plis": n_label_plis,
        "n_scope_correct": n_scope_correct,
        "n_with_label": n_with_label,
        "n_predicted": n_predicted,
        "n_matched": n_matched,
        "per_canonical": per_canonical,
        "e2e_pli_count": e2e_plis,
    }


def _count_anchor_col_values(grid: list[list], col: int) -> int:
    """Crude: count non-trivial values in a column from row 3 down, stopping
    at long blank runs. Starts at row 3 to skip 1-2 header rows."""
    cnt = 0
    blanks = 0
    seen_any = False
    for r in range(3, len(grid) + 1):
        row = grid[r - 1]
        if col - 1 < len(row):
            v = row[col - 1].value
        else:
            v = None
        if v is None or (isinstance(v, str) and v.strip() == ""):
            blanks += 1
            if seen_any and blanks >= 3:
                break
            continue
        # skip "Grand Total"
        if isinstance(v, str) and "total" in v.lower() and len(v) <= 20:
            continue
        # skip cells that look like further headers (short ALL-CAPS text)
        if isinstance(v, str) and v.strip().isupper() and len(v.strip()) <= 12 and not any(ch.isdigit() for ch in v):
            continue
        cnt += 1
        seen_any = True
        blanks = 0
    return cnt
