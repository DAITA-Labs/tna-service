"""Survey tools — cheap, no cell reads."""
from __future__ import annotations
from app.models.workbook import WorkbookCtx, SheetMeta
from app.models.artifacts import WorkbookSummary
from app.repositories.workbook_tools._registry import tool


@tool("list_sheets")
def list_sheets(ctx: WorkbookCtx) -> list[SheetMeta]:
    """Return name + dimensions for every sheet in the workbook."""
    out = []
    for name in ctx.wb.sheetnames:
        ws = ctx.wb[name]
        out.append(SheetMeta(
            name=name,
            max_row=ws.max_row or 0,
            max_col=ws.max_column or 0,
            dimensions=ws.dimensions,
        ))
    return out


@tool("workbook_summary")
def workbook_summary(ctx: WorkbookCtx) -> WorkbookSummary:
    """High-level workbook shape — count, names, file size."""
    size_kb = ctx.path.stat().st_size // 1024
    return WorkbookSummary(
        sheet_count=len(ctx.wb.sheetnames),
        sheet_names=list(ctx.wb.sheetnames),
        file_size_kb=size_kb,
    )
