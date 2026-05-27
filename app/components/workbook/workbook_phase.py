"""WorkbookPhase orchestrator — workbook → list[ClusterAnchorBundle].

`run_workbook_phase(workbook)` drives the routing layer end-to-end:

  1. profile every sheet                 (`compute_sheet_signature`)
  2. cluster sheets by template          (`cluster_sheets`)
  3. for each cluster:
       a. pick its anchor sheet          (`pick_anchor_sheet_name`)
       b. run the structure phase        (`run_structure_phase`)
       c. classify the cluster's role    (`classify_cluster_role`)
  4. keep only clusters whose role is `pli_cluster`
  5. return one `ClusterAnchorBundle` per surviving cluster

`ClusterAnchorBundle` is the handoff artifact for field components:
they take a bundle, read the hint to locate identifiers, and use the
canvas + bag for spatial reasoning.
"""
from __future__ import annotations

from haystack import component

from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.structure.phase import run_structure_phase
from app.components.workbook.anchor_picker import pick_anchor_sheet_name
from app.components.workbook.clusterer import cluster_sheets
from app.components.workbook.profiler import compute_sheet_signature
from app.components.workbook.role_classifier import (
    classify_cluster_role,
    filter_pli_clusters,
)


def run_workbook_phase(workbook) -> list[ClusterAnchorBundle]:
    """Profile + cluster + classify + anchor + structure-phase the workbook.

    Returns one `ClusterAnchorBundle` per `pli_cluster` after role
    classification. Non-PLI clusters are dropped.
    """
    signatures = [compute_sheet_signature(ws) for ws in workbook.worksheets]
    clusters = cluster_sheets(signatures)
    sheets_by_name = {ws.title: ws for ws in workbook.worksheets}

    bundles: list[ClusterAnchorBundle] = []
    for cluster in clusters:
        anchor_name = pick_anchor_sheet_name(cluster, signatures)
        if anchor_name is None:
            continue
        anchor_sheet = sheets_by_name[anchor_name]
        canvas, bag, hint = run_structure_phase(anchor_sheet, cluster_id=cluster.cluster_id)
        classify_cluster_role(cluster, canvas, bag)
        bundles.append(ClusterAnchorBundle(
            cluster=cluster,
            anchor_sheet_name=anchor_name,
            canvas=canvas, bag=bag, hint=hint,
        ))

    # Drop other_sheets/unknown — caller only sees pli_cluster bundles.
    pli_cluster_ids = {c.cluster_id for c in filter_pli_clusters(clusters)}
    return [b for b in bundles if b.cluster.cluster_id in pli_cluster_ids]


@component
class WorkbookPhase(Component):
    """Haystack wrapper around `run_workbook_phase`.

    Inputs:
        workbook — an openpyxl Workbook

    Outputs:
        bundles — list[ClusterAnchorBundle], one per pli_cluster after
                   role classification
    """

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(bundles=list[ClusterAnchorBundle])
    def run(self, workbook) -> dict:
        return {"bundles": run_workbook_phase(workbook)}
