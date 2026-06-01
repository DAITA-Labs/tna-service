"""WorkbookPhase orchestrator — workbook → list[ClusterAnchorBundle].

`run_workbook_phase(workbook)` drives the routing layer end-to-end:

  1. profile every sheet                 (`compute_sheet_signature`)
  2. cluster sheets by template          (`cluster_sheets`)
  3. for each cluster:
       a. pick its anchor sheet          (`pick_anchor_sheet_name`)
       b. run the structure phase        (`run_structure_phase`)
       c. build canvases for every sibling sheet so the cluster's
          plan can be applied to each member in turn

`ClusterAnchorBundle` is the handoff artifact for the planning + applier
layer: structure phase outputs (canvas / bag / hint) come from the
anchor sheet; `sibling_canvases` carries every other sheet in the
cluster so per-sheet PLIs can flow out of multi-sheet clusters.

The workbook handed to this phase is assumed to be operator-curated —
every sheet in the workbook is expected to contribute PLI data, so
no role filter runs here. Empty / structurally-foreign sheets fall
into singleton clusters and contribute no PLIs downstream.
"""
from __future__ import annotations

from haystack import component

from app.artifacts.canvas import GridCanvas
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.structure.phase import run_structure_phase
from app.components.workbook.anchor_picker import pick_anchor_sheet_name
from app.components.workbook.clusterer import cluster_sheets
from app.components.workbook.profiler import compute_sheet_signature
from app.tools.canvas.build import build_canvas


def run_workbook_phase(workbook) -> list[ClusterAnchorBundle]:
    """Profile + cluster + structure-phase the workbook.

    Returns one `ClusterAnchorBundle` per cluster. The bundle's
    `sibling_canvases` carries the cluster's other member sheets'
    canvases so the applier can iterate them with the cluster's
    shared plan.
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
        siblings: dict[str, GridCanvas] = {
            name: build_canvas(sheets_by_name[name])
            for name in cluster.sheet_names
            if name != anchor_name and name in sheets_by_name
        }
        bundles.append(ClusterAnchorBundle(
            cluster=cluster,
            anchor_sheet_name=anchor_name,
            canvas=canvas, bag=bag, hint=hint,
            sibling_canvases=siblings,
        ))
    return bundles


@component
class WorkbookPhase(Component):
    """Haystack wrapper around `run_workbook_phase`.

    Inputs:
        workbook — an openpyxl Workbook

    Outputs:
        bundles — list[ClusterAnchorBundle], one per cluster
    """

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(bundles=list[ClusterAnchorBundle])
    def run(self, workbook) -> dict:
        return {"bundles": run_workbook_phase(workbook)}
