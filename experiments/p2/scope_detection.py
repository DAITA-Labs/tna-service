"""Scope detection — infer FieldScope (SHEET / GROUP / PLI) from candidates.

Given the deterministic candidates produced by find_field_locations + the
shape signals + an estimated pli_count, decide whether the field is:
  - SHEET-scoped (one cell broadcast to all PLIs),
  - PLI-scoped (column anchored with N values OR one cell per PLI region), or
  - GROUP-scoped (multiple candidates each shared by a subset).

Three variants:
    A — cardinality_only: count of candidates → scope
    B — region_based: position relative to biggest_rect → scope
    C — combined: both signals weighted
"""
from __future__ import annotations

from openpyxl.utils.cell import get_column_letter

from experiments.specs.enums import FieldScope, ReadDirection
from experiments.specs.schemas import FieldLocator, ReadPattern

from experiments.p1.shape_models import ShapeSummary

from .locator_models import DetectedFieldLocation, ScopeDecision


def _is_column_anchored(cand: DetectedFieldLocation) -> bool:
    return cand.kind == "column_header" and bool(cand.column_values)


def _top_of_sheet(cand: DetectedFieldLocation, shape: ShapeSummary) -> bool:
    """Is the candidate's label *above* the data rectangle (a kv block)?"""
    if shape.biggest_rect is None:
        return False
    return cand.label_row < shape.biggest_rect.r0


def _inside_rect(cand: DetectedFieldLocation, shape: ShapeSummary) -> bool:
    r = shape.biggest_rect
    if r is None:
        return False
    return r.r0 <= cand.label_row <= r.r1 and r.c0 <= cand.label_col <= r.c1


# =============================================================================
# Variant A — cardinality only
# =============================================================================


def scope_cardinality_only(
    candidates: list[DetectedFieldLocation],
    pli_count: int,
) -> ScopeDecision:
    if not candidates:
        return ScopeDecision(
            canonical="?",
            scope=FieldScope.PLI,
            reason="no candidates",
        )
    canonical = candidates[0].canonical
    # one column-anchored → PLI
    col_anchored = [c for c in candidates if _is_column_anchored(c)]
    if col_anchored and pli_count > 1:
        winner = col_anchored[0]
        return ScopeDecision(
            canonical=canonical,
            scope=FieldScope.PLI,
            chosen=winner,
            competing=[c for c in candidates if c is not winner][:3],
            reason="column-anchored header → PLI",
            confidence=0.9,
        )
    if len(candidates) == 1:
        return ScopeDecision(
            canonical=canonical,
            scope=FieldScope.SHEET,
            chosen=candidates[0],
            reason="1 candidate → SHEET",
            confidence=0.85,
        )
    if pli_count > 0 and len(candidates) == pli_count:
        return ScopeDecision(
            canonical=canonical,
            scope=FieldScope.PLI,
            chosen=candidates[0],
            competing=candidates[1:pli_count],
            reason=f"{len(candidates)} candidates = pli_count → PLI",
            confidence=0.8,
        )
    if pli_count > 1 and 1 < len(candidates) < pli_count:
        return ScopeDecision(
            canonical=canonical,
            scope=FieldScope.GROUP,
            chosen=candidates[0],
            competing=candidates[1:],
            reason="N candidates between 1 and pli_count → GROUP",
            confidence=0.5,
        )
    # ambiguous — default PLI optimistically
    return ScopeDecision(
        canonical=canonical,
        scope=FieldScope.PLI,
        chosen=candidates[0],
        competing=candidates[1:5],
        reason="ambiguous; default PLI",
        confidence=0.3,
    )


# =============================================================================
# Variant B — region based
# =============================================================================


def scope_region_based(
    candidates: list[DetectedFieldLocation],
    shape: ShapeSummary,
    pli_count: int,
) -> ScopeDecision:
    if not candidates:
        return ScopeDecision(canonical="?", scope=FieldScope.PLI, reason="no candidates")
    canonical = candidates[0].canonical
    col_anchored = [c for c in candidates if _is_column_anchored(c)]
    top_of_sheet = [c for c in candidates if _top_of_sheet(c, shape)]
    in_rect = [c for c in candidates if _inside_rect(c, shape)]

    # Strongest signal: a column-header inside/around the biggest rect
    if col_anchored:
        winner = col_anchored[0]
        non_blank_count = sum(
            1 for v in winner.column_values
            if v is not None and not (isinstance(v, str) and v.strip() == "")
        )
        # If the column has only 1 non-blank value, it's effectively
        # SHEET-scope (the value broadcasts to all PLIs).
        if pli_count > 1 and non_blank_count >= 2:
            return ScopeDecision(
                canonical=canonical,
                scope=FieldScope.PLI,
                chosen=winner,
                competing=[c for c in candidates if c is not winner][:3],
                reason=f"column header with {non_blank_count} non-blank values → PLI",
                confidence=0.9,
            )
        return ScopeDecision(
            canonical=canonical,
            scope=FieldScope.SHEET,
            chosen=winner,
            reason="column header with one non-blank value → SHEET",
            confidence=0.7,
        )

    if top_of_sheet and not in_rect:
        # KV block above the data → SHEET
        winner = top_of_sheet[0]
        return ScopeDecision(
            canonical=canonical,
            scope=FieldScope.SHEET,
            chosen=winner,
            competing=top_of_sheet[1:3],
            reason="kv-label above data rectangle → SHEET",
            confidence=0.8,
        )

    if len(candidates) > 1 and pli_count > 1 and len(candidates) < pli_count:
        winner = candidates[0]
        return ScopeDecision(
            canonical=canonical,
            scope=FieldScope.GROUP,
            chosen=winner,
            competing=candidates[1:],
            reason="N candidates < pli_count → GROUP",
            confidence=0.4,
        )

    # Fall through to cardinality logic
    return scope_cardinality_only(candidates, pli_count)


# =============================================================================
# Variant C — combined
# =============================================================================


def scope_combined(
    candidates: list[DetectedFieldLocation],
    shape: ShapeSummary,
    pli_count: int,
) -> ScopeDecision:
    """Take region as primary signal, fall back to cardinality."""
    region = scope_region_based(candidates, shape, pli_count)
    if region.confidence >= 0.6:
        return region
    card = scope_cardinality_only(candidates, pli_count)
    # If region is GROUP but cardinality says SHEET (e.g. only 1 surviving
    # candidate after dedupe), prefer cardinality.
    if region.scope == FieldScope.GROUP and card.scope == FieldScope.SHEET:
        return card
    # Otherwise blend confidences and report the region's scope.
    region.confidence = max(region.confidence, card.confidence * 0.8)
    return region


# =============================================================================
# Build FieldLocator from a ScopeDecision
# =============================================================================


def build_field_locator(
    decision: ScopeDecision, axis_hint: str = "row",
) -> FieldLocator | None:
    """Convert a scope decision into a FieldLocator (None when no chosen cand)."""
    if decision.chosen is None:
        return None
    cand = decision.chosen
    if decision.scope == FieldScope.SHEET:
        return FieldLocator(
            canonical=decision.canonical,
            scope=FieldScope.SHEET,
            read_pattern=ReadPattern(
                direction=ReadDirection.FIXED,
                fixed_cell=cand.value_cell,
            ),
            confidence=decision.confidence,
            notes=decision.reason,
        )
    if decision.scope == FieldScope.PLI:
        if _is_column_anchored(cand):
            # Column-anchored — apply_plan reads (pli_anchor_row, anchor_col)
            return FieldLocator(
                canonical=decision.canonical,
                scope=FieldScope.PLI,
                read_pattern=ReadPattern(
                    direction=ReadDirection.SAME_ROW,
                    anchor_col=get_column_letter(cand.value_col or cand.label_col),
                ),
                confidence=decision.confidence,
                notes=decision.reason,
            )
        # KV PLI — for SECTION_PER_PLI / SHEET_IS_PLI per-PLI fields. apply_plan
        # would need a per-PLI offset; we just pin to a fixed cell with a note.
        return FieldLocator(
            canonical=decision.canonical,
            scope=FieldScope.PLI,
            read_pattern=ReadPattern(
                direction=ReadDirection.FIXED,
                fixed_cell=cand.value_cell,
            ),
            confidence=decision.confidence,
            notes=decision.reason + " (single-cell PLI; sheet-level treated as 1 PLI)",
        )
    if decision.scope == FieldScope.GROUP:
        return FieldLocator(
            canonical=decision.canonical,
            scope=FieldScope.GROUP,
            read_pattern=None,
            group_id="auto",
            confidence=decision.confidence,
            notes=decision.reason,
        )
    return None
