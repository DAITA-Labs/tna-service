"""Anchor picker — choose which sheet in a cluster serves as the structure-phase template.

The anchor sheet is the one we actually run `run_structure_phase` against;
the rest of the cluster's sheets inherit the resulting `LayoutHint` and
are processed by field components against their own canvases.

Selection rule:

  Pick the sheet whose signature has the *most* populated cells in the
  sample window (`non_blank_mask` size). The richest sheet usually carries
  the cleanest header row + the most data rows, so its structure-phase
  output transfers best to its siblings.

  Ties are broken by sheet order in the workbook (earlier wins) so the
  choice is stable across reruns.

Empty clusters yield `None`. Single-sheet clusters trivially pick their
only sheet.
"""
from __future__ import annotations

from haystack import component

from app.artifacts.workbook import PliCluster, SheetSignature
from app.components._base import Component


def pick_anchor_sheet_name(cluster: PliCluster,
                              signatures: list[SheetSignature]) -> str | None:
    """Return the sheet name to anchor the structure phase on, or None for empty clusters."""
    if not cluster.sheet_names:
        return None

    by_name = {sig.sheet_name: sig for sig in signatures}
    in_cluster = [name for name in cluster.sheet_names if name in by_name]
    if not in_cluster:
        return None

    # Earlier sheets win ties — iterate in cluster order, keep first richest.
    best_name = in_cluster[0]
    best_score = len(by_name[best_name].non_blank_mask)
    for name in in_cluster[1:]:
        score = len(by_name[name].non_blank_mask)
        if score > best_score:
            best_name, best_score = name, score
    return best_name


@component
class AnchorPicker(Component):
    """Haystack wrapper around `pick_anchor_sheet_name` for one cluster.

    Inputs:
        cluster    — the PliCluster to pick an anchor for
        signatures — every SheetSignature in the workbook

    Outputs:
        anchor_sheet_name — chosen anchor (str) or None if no candidates
    """

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(anchor_sheet_name=str)
    def run(self, cluster: PliCluster, signatures: list[SheetSignature]) -> dict:
        return {"anchor_sheet_name": pick_anchor_sheet_name(cluster, signatures)}
