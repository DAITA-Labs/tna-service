"""IdentifierExtractor — runs find_field_locations × 9 specs and reconciles.

Reconciliation rules:
  1. For each spec, ask find_field_locations for candidates.
  2. Cross-spec dedupe: if the same value_cell wins for two canonicals, keep
     the higher combined_score. This handles 'Color' alias being shared by
     color_code and color_name — dtype-based scoring picks the right one.
  3. For each spec, run scope detection (variant configurable) to produce
     a ScopeDecision + FieldLocator.
"""
from __future__ import annotations

from collections import defaultdict

from experiments.p1.shape_models import ShapeSummary
from experiments.specs.identifiers import IDENTIFIER_SPECS
from experiments.specs.enums import PliMode

from .find_field_locations import find_field_locations
from .locator_models import (
    DetectedFieldLocation,
    FieldLocator,
    IdentifierExtractionResult,
    ScopeDecision,
)
from .scope_detection import (
    build_field_locator,
    scope_cardinality_only,
    scope_combined,
    scope_region_based,
)


def run_identifier_extractor(
    file_name: str,
    sheet_name: str,
    grid: list[list],
    shape: ShapeSummary,
    pli_mode: PliMode | None,
    pli_count_label: int,
    *,
    label_strategy: str = "combined_weighted",
    dtype_strategy: str = "strict",
    scope_strategy: str = "combined",
) -> IdentifierExtractionResult:
    """Run identifier extraction × all 9 specs."""

    # Phase 1 — gather candidates per spec
    raw_candidates: dict[str, list[DetectedFieldLocation]] = {}
    for spec in IDENTIFIER_SPECS:
        cands = find_field_locations(
            grid, shape, spec,
            label_strategy=label_strategy,
            dtype_strategy=dtype_strategy,
        )
        raw_candidates[spec.canonical] = cands

    # Phase 2 — cross-spec conflict resolution. If the same value_cell appears
    # as the top candidate for two specs, keep the higher combined_score.
    # This is critical for 'Color' (color_code vs color_name) — vocab matches
    # both, dtype scoring breaks the tie.
    top_by_cell: dict[str, tuple[str, float]] = {}  # value_cell -> (canonical, score)
    for canonical, cands in raw_candidates.items():
        if not cands:
            continue
        top = cands[0]
        if top.value_cell is None:
            continue
        key = top.value_cell
        prev = top_by_cell.get(key)
        if prev is None or top.combined_score > prev[1]:
            top_by_cell[key] = (canonical, top.combined_score)

    # Now demote any spec whose top candidate is owned by another canonical.
    candidates_per_canonical: dict[str, list[DetectedFieldLocation]] = {}
    for canonical, cands in raw_candidates.items():
        kept: list[DetectedFieldLocation] = []
        for c in cands:
            if c.value_cell and c.value_cell in top_by_cell:
                owner, _ = top_by_cell[c.value_cell]
                if owner != canonical:
                    continue  # cell belongs to another canonical
            kept.append(c)
        candidates_per_canonical[canonical] = kept

    # Phase 3 — scope detection per canonical
    scope_decisions: dict[str, ScopeDecision] = {}
    field_locators: dict[str, FieldLocator] = {}

    if scope_strategy == "cardinality_only":
        def _decide(cands, _shape, _count):
            return scope_cardinality_only(cands, _count)
    elif scope_strategy == "region_based":
        def _decide(cands, _shape, _count):
            return scope_region_based(cands, _shape, _count)
    else:
        def _decide(cands, _shape, _count):
            return scope_combined(cands, _shape, _count)

    for spec in IDENTIFIER_SPECS:
        cands = candidates_per_canonical[spec.canonical]
        if not cands:
            continue
        decision = _decide(cands, shape, pli_count_label)
        decision.canonical = spec.canonical
        scope_decisions[spec.canonical] = decision
        locator = build_field_locator(decision)
        if locator is not None:
            field_locators[spec.canonical] = locator

    warnings: list[str] = []
    # Mandatory check
    for spec in IDENTIFIER_SPECS:
        if spec.mandatory and spec.canonical not in field_locators:
            warnings.append(f"mandatory field missing: {spec.canonical}")

    return IdentifierExtractionResult(
        file=file_name,
        sheet_name=sheet_name,
        pli_mode=pli_mode,
        pli_count_label=pli_count_label,
        candidates_per_canonical=candidates_per_canonical,
        scope_decisions=scope_decisions,
        field_locators=field_locators,
        warnings=warnings,
    )
