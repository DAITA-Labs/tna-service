"""MetadataAssembler — produce metadata MetadataPlan entries from the bag.

Honours the "no silent data loss" principle. Two sources feed the
output:

  1. **KvBlocks** — every `KvBlock` on `bag.kv_blocks` not already
     claimed by an identifier picker becomes a
     `MetadataPlan(mode=KV_BLOCK, scope=SHEET, dir=FIXED)`.
  2. **Unclaimed columns** — every column inside the header band whose
     anchor cell carries text AND that wasn't claimed by an identifier
     picker becomes a `MetadataPlan(mode=COLUMN, scope=PLI, dir=SAME_ROW)`.

The label / header text becomes `header_text` (the key); if it matches
a `METADATA_SPECS` alias the `canonical` is set.
"""
from __future__ import annotations

from typing import Any

from haystack import component

from app.artifacts.plan import MetadataPlan
from app.artifacts.structure import KvBlock
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.enums.field_location_mode import FieldLocationMode
from app.enums.field_scope import FieldScope
from app.enums.read_direction import ReadDirection
from app.specs import METADATA_SPECS


@component
class MetadataAssembler(Component):
    """Emit MetadataPlan entries for unclaimed KvBlocks AND unclaimed columns."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(metadata_entries=list[MetadataPlan])
    def run(
        self,
        bundle:             ClusterAnchorBundle,
        claimed_kv_blocks:  set[KvBlock] | None = None,
        claimed_columns:    set[int]    | None = None,
    ) -> dict:
        entries: list[MetadataPlan] = []
        entries.extend(_kv_metadata(bundle, claimed_kv_blocks or set()))
        entries.extend(_unclaimed_column_metadata(bundle, claimed_columns or set()))
        return {"metadata_entries": entries}


# ── kv-block path ──────────────────────────────────────────────────────────


def _kv_metadata(
    bundle:  ClusterAnchorBundle,
    claimed: set[KvBlock],
) -> list[MetadataPlan]:
    out: list[MetadataPlan] = []
    for kv in bundle.bag.kv_blocks:
        if kv in claimed:
            continue
        out.append(MetadataPlan(
            header_text=kv.label_text,
            canonical=_match_canonical(kv.label_text),
            mode=FieldLocationMode.KV_BLOCK,
            scope=FieldScope.SHEET,
            read_direction=ReadDirection.FIXED,
            kv_block=kv,
        ))
    return out


# ── unclaimed-column path ─────────────────────────────────────────────────


def _unclaimed_column_metadata(
    bundle:  ClusterAnchorBundle,
    claimed: set[int],
) -> list[MetadataPlan]:
    """Every header-bearing column not won by an identifier picker → metadata column."""
    band = bundle.hint.header_band
    if band is None:
        return []
    header_row_idx = band.rect.r0 - 1   # 1-indexed → 0-indexed for canvas access
    if header_row_idx < 0 or header_row_idx >= bundle.canvas.n_rows:
        return []

    out: list[MetadataPlan] = []
    for col in range(band.rect.c0, band.rect.c1 + 1):
        if col in claimed:
            continue
        header_text = _read_header_text(bundle, header_row_idx, col)
        if header_text is None:
            continue
        out.append(MetadataPlan(
            header_text=header_text,
            canonical=_match_canonical(header_text),
            mode=FieldLocationMode.COLUMN,
            scope=FieldScope.PLI,
            read_direction=ReadDirection.SAME_ROW,
            column=col,
        ))
    return out


def _read_header_text(
    bundle:         ClusterAnchorBundle,
    header_row_idx: int,
    col:            int,
) -> str | None:
    """Return the header text at (header_row_idx, col-1), or None if empty/non-string."""
    col_idx = col - 1
    if col_idx < 0 or col_idx >= bundle.canvas.n_cols:
        return None
    value = bundle.canvas.cell_values[header_row_idx][col_idx]
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


# ── canonical matching ────────────────────────────────────────────────────


def _match_canonical(label_text: str) -> str | None:
    """Exact case-insensitive match against any METADATA_SPECS alias."""
    needle = (label_text or "").strip().lower()
    if not needle:
        return None
    for spec in METADATA_SPECS:
        if needle in {alias.lower() for alias in spec.aliases}:
            return spec.canonical
    return None
