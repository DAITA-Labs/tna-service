"""StructurePhase orchestrator — sheet → (canvas, bag, LayoutHint).

Chains every Tier 1 + Tier 2 step into a single top-level function:

  1. build_canvas              (Tier 1a)  — openpyxl sheet → 21-channel canvas
  2. populate_patterns         (Tier 1b–1d) — every strip detector
  3. populate_semantics        (Tier 2a)  — six resolvers in dep order
  4. infer_layout_axes         (Tier 2b)  — three orthogonal axes
  5. compose_layout_hint       (Tier 2b)  — bundle into a LayoutHint

This is the single public entry point Tier 3 (workbook phase) and Tier 4
(field components) will call. Returning the trio `(canvas, bag, hint)`
lets downstream code reach back into the canvas for cell values and into
the bag for any record the LayoutHint doesn't surface directly.

Anchor-sheet selection (which sheet in a `pli_cluster` runs this phase)
and inheritance verification (whether other sheets in the cluster match
the anchor's hint) live in Tier 3 — they presume a cluster artifact that
doesn't yet exist.
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutHint
from app.artifacts.structure import StructureBag
from app.components.structure.axis_inferrer import infer_layout_axes
from app.components.structure.layout_composer import compose_layout_hint
from app.components.structure.populate import populate_patterns, populate_semantics
from app.tools.canvas.build import build_canvas


def run_structure_phase(sheet, cluster_id: str = "default") -> tuple[GridCanvas, StructureBag, LayoutHint]:
    """Run every structure-phase step against a single openpyxl sheet.

    Args:
        sheet:      openpyxl worksheet
        cluster_id: pli_cluster identifier propagated onto the LayoutHint
                    (defaults to "default" for single-sheet smoke tests)

    Returns:
        canvas — the 21-channel GridCanvas for downstream cell reads
        bag    — the StructureBag with every pattern + semantic record
        hint   — the LayoutHint field components consume
    """
    canvas = build_canvas(sheet)
    bag = StructureBag()
    populate_patterns(canvas, bag)
    populate_semantics(canvas, bag)
    axes = infer_layout_axes(canvas, bag)
    hint = compose_layout_hint(canvas, bag, axes, cluster_id=cluster_id)
    return canvas, bag, hint
