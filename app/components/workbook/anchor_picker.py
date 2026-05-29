"""Anchor picker — choose which sheet in a cluster serves as the structure-phase template.

The anchor sheet is the one we run `run_structure_phase` against; the
rest of the cluster's sheets inherit the resulting `LayoutHint` and
are processed by field components against their own canvases.

Implementation delegates to `AnchorSheetPicker`
(`app/components/pickers/anchor_sheet.py`). Selection rule (preserved):
pick the sheet whose `non_blank_mask` is largest; ties broken by cluster
order. New policies — date-strip count, identifier-alias matches —
land on the picker without changing this facade.

Empty clusters yield `None`. Single-sheet clusters trivially pick their
only sheet.
"""
from __future__ import annotations

from haystack import component

from app.artifacts.workbook import PliCluster, SheetSignature
from app.components._base import Component
from app.components.pickers.anchor_sheet import AnchorSheetPicker


def pick_anchor_sheet_name(
    cluster:    PliCluster,
    signatures: list[SheetSignature],
) -> str | None:
    """Return the sheet name to anchor the structure phase on, or None for empty clusters."""
    return AnchorSheetPicker().run(cluster=cluster, signatures=signatures)["anchor_sheet_name"]


@component
class AnchorPicker(Component):
    """Haystack wrapper around `pick_anchor_sheet_name` for one cluster."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(anchor_sheet_name=str)
    def run(self, cluster: PliCluster, signatures: list[SheetSignature]) -> dict:
        return {"anchor_sheet_name": pick_anchor_sheet_name(cluster, signatures)}
