"""AnchorSheetPicker — pick the anchor sheet for a cluster's structure phase.

Drop-in successor to `pick_anchor_sheet_name` in
`app/components/workbook/anchor_picker.py`. Same ranking — sheet with
the largest non-blank-mask wins — re-expressed as a Picker so more
policies can be added without touching the picker class.

Tie-break preserves legacy behaviour: cluster-order wins, since
`Picker._score_candidates` uses `max()` which returns the first
encountered for equal scores.
"""
from __future__ import annotations

from typing import Any, Sequence

from haystack import component

from app.artifacts.workbook import PliCluster, SheetSignature
from app.components.pickers._base import Picker
from app.policies._base import PolicyVerdict
from app.policies.workbook.anchor_sheet import prefer_richer_sheet


@component
class AnchorSheetPicker(Picker[str]):
    """Pick which sheet in a cluster anchors the structure phase."""

    def __init__(self) -> None:
        Picker.__init__(
            self,
            policies=[prefer_richer_sheet],
            score_floor=0.0,
        )

    def candidates(
        self,
        cluster:            PliCluster,
        signatures_by_name: dict[str, SheetSignature],
    ) -> Sequence[str]:
        """Only sheets present in both the cluster AND the signatures map are candidates."""
        return [name for name in cluster.sheet_names if name in signatures_by_name]

    @component.output_types(
        anchor_sheet_name=str,
        verdicts=list[PolicyVerdict],
    )
    def run(
        self,
        cluster:    PliCluster,
        signatures: list[SheetSignature],
    ) -> dict:
        signatures_by_name = {sig.sheet_name: sig for sig in signatures}
        cands              = self.candidates(cluster, signatures_by_name)
        if not cands:
            return {"anchor_sheet_name": None, "verdicts": []}
        winner, verdicts = self._score_candidates(
            cands,
            signatures_by_name=signatures_by_name,
        )
        return {"anchor_sheet_name": winner, "verdicts": verdicts}
