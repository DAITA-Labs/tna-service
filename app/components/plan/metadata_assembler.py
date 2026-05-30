"""MetadataAssembler — produce metadata MetadataPlan entries from kv blocks.

Honours the "no silent data loss" principle: every `KvBlock` the
detector found that isn't already claimed by an identifier picker
becomes a `MetadataPlan(mode=KV_BLOCK, scope=SHEET, dir=FIXED)`. The
label text becomes the `header_text` (the key); if the label matches
a `METADATA_SPECS` alias the `canonical` is set.

Unclaimed-column metadata (tabular columns without a winning identifier)
is deferred to a follow-up — needs a "column has a text header" probe
that doesn't lean on the legacy finding-builder.
"""
from __future__ import annotations

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
    """Emit MetadataPlan entries for every unclaimed KvBlock on the bag."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(metadata_entries=list[MetadataPlan])
    def run(
        self,
        bundle:             ClusterAnchorBundle,
        claimed_kv_blocks:  set[KvBlock] | None = None,
    ) -> dict:
        claimed = claimed_kv_blocks or set()
        entries: list[MetadataPlan] = []
        for kv in bundle.bag.kv_blocks:
            if kv in claimed:
                continue
            entries.append(MetadataPlan(
                header_text=kv.label_text,
                canonical=_match_canonical(kv.label_text),
                mode=FieldLocationMode.KV_BLOCK,
                scope=FieldScope.SHEET,
                read_direction=ReadDirection.FIXED,
                kv_block=kv,
            ))
        return {"metadata_entries": entries}


def _match_canonical(label_text: str) -> str | None:
    """Exact case-insensitive match against any METADATA_SPECS alias."""
    needle = (label_text or "").strip().lower()
    if not needle:
        return None
    for spec in METADATA_SPECS:
        if needle in {alias.lower() for alias in spec.aliases}:
            return spec.canonical
    return None
