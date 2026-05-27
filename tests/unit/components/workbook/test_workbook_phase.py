"""WorkbookPhase orchestrator — workbook → list[ClusterAnchorBundle]."""
from __future__ import annotations

import datetime as dt

import openpyxl
from haystack import Pipeline
from openpyxl.styles import Font

from app.artifacts.workbook import ClusterAnchorBundle
from app.components.workbook.workbook_phase import WorkbookPhase, run_workbook_phase


def _tabular_pli_sheet(ws, prefix: str) -> None:
    """Populate `ws` with a small PLI-shaped table (header + 5 rows + date col)."""
    for c, h in enumerate(["IO No", "Style", "Qty", "Delivery"], start=1):
        cell = ws.cell(row=2, column=c, value=h)
        cell.font = Font(bold=True)
    for r in range(3, 8):
        ws.cell(row=r, column=1, value=f"{prefix}-{r}")
        ws.cell(row=r, column=2, value=f"S{r}")
        ws.cell(row=r, column=3, value=100 + r)
        ws.cell(row=r, column=4, value=dt.date(2026, 5, r))


def _other_sheet(ws) -> None:
    """A metadata-shaped sheet — no dates, no PLI signals."""
    ws.cell(row=1, column=1, value="Buyer")
    ws.cell(row=1, column=2, value="Acme")
    ws.cell(row=2, column=1, value="Season")
    ws.cell(row=2, column=2, value="FW26")


def _workbook(*sheet_specs):
    """Build a workbook with one sheet per (title, populate_fn) pair."""
    wb = openpyxl.Workbook()
    default = wb.active
    if sheet_specs:
        default.title = sheet_specs[0][0]
        sheet_specs[0][1](default)
    for title, populate in sheet_specs[1:]:
        ws = wb.create_sheet(title=title)
        populate(ws)
    return wb


def test_run_workbook_phase_returns_bundles_per_pli_cluster() -> None:
    wb = _workbook(
        ("PLI-1", lambda ws: _tabular_pli_sheet(ws, "P1")),
        ("PLI-2", lambda ws: _tabular_pli_sheet(ws, "P2")),
        ("Info", _other_sheet),
    )
    bundles = run_workbook_phase(wb)

    assert all(isinstance(b, ClusterAnchorBundle) for b in bundles)
    assert all(b.cluster.role == "pli_cluster" for b in bundles)
    # The metadata-shaped sheet must not appear as an anchor
    assert all(b.anchor_sheet_name != "Info" for b in bundles)


def test_other_sheets_dropped_from_results() -> None:
    """A workbook where every sheet is non-PLI yields an empty bundle list."""
    wb = _workbook(("Info", _other_sheet))
    assert run_workbook_phase(wb) == []


def test_bundle_propagates_cluster_id_onto_hint() -> None:
    wb = _workbook(("PLI-A", lambda ws: _tabular_pli_sheet(ws, "PA")))
    bundles = run_workbook_phase(wb)
    assert len(bundles) == 1
    assert bundles[0].hint.cluster_id == bundles[0].cluster.cluster_id


def test_workbook_phase_component_returns_bundles() -> None:
    wb = _workbook(("PLI-A", lambda ws: _tabular_pli_sheet(ws, "PA")))
    out = WorkbookPhase().run(workbook=wb)
    assert set(out.keys()) == {"bundles"}
    assert len(out["bundles"]) == 1


def test_workbook_phase_component_sockets() -> None:
    comp = WorkbookPhase()
    assert "workbook" in comp.__haystack_input__._sockets_dict
    assert "bundles" in comp.__haystack_output__._sockets_dict


def test_workbook_phase_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("workbook_phase", WorkbookPhase())
    assert "workbook_phase" in pipeline.graph.nodes
