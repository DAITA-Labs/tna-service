"""StructurePhase orchestrator — sheet → (canvas, bag, LayoutHint).

`run_structure_phase` is the single public entry point for the structure
phase. It composes five steps:

  1. `build_canvas`           — openpyxl sheet → 21-channel canvas
  2. `populate_patterns`      — every strip detector → bag pattern fields
  3. `populate_semantics`     — six resolvers in dependency order
  4. `infer_layout_axes`      — three orthogonal axes
  5. `compose_layout_hint`    — bundle into a LayoutHint

Returns the trio `(canvas, bag, hint)` so downstream consumers (workbook
routing and field components) can reach back into the canvas for cell
values and into the bag for any record the LayoutHint doesn't surface
directly.

Anchor-sheet selection (choosing which sheet in a `pli_cluster` runs
this phase) and inheritance verification (whether other sheets in the
cluster match the anchor's hint) are not handled here — they presume a
cluster artifact emitted by the workbook layer.
"""
from __future__ import annotations

from haystack import component

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutHint
from app.artifacts.structure import StructureBag
from app.components._base import Component
from app.components.structure.axis_inferrer import infer_layout_axes
from app.components.structure.layout_composer import compose_layout_hint
from app.components.structure.populate import populate_patterns, populate_semantics
from app.tools.canvas.build import build_canvas


def run_structure_phase(sheet, cluster_id: str = "default") -> tuple[GridCanvas, StructureBag, LayoutHint]:
    """Run every structure-phase step against a single openpyxl sheet.

    Args:
        sheet:      openpyxl worksheet
        cluster_id: `pli_cluster` identifier propagated onto the LayoutHint
                    (defaults to "default" for single-sheet callers)

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


@component
class StructurePhase(Component):
    """Haystack wrapper around `run_structure_phase`.

    Inputs:
        sheet      — an openpyxl worksheet
        cluster_id — the `pli_cluster` id (defaults to "default")

    Outputs:
        canvas / bag / hint — the three artifacts the structure phase emits.
    """

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(canvas=GridCanvas, bag=StructureBag, hint=LayoutHint)
    def run(self, sheet, cluster_id: str = "default") -> dict:
        canvas, bag, hint = run_structure_phase(sheet, cluster_id=cluster_id)
        return {"canvas": canvas, "bag": bag, "hint": hint}
