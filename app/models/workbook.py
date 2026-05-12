"""Workbook representation models — Pydantic, pure domain.

Cell / MergedRegion / CellGrid / SheetMeta are the typed values tools return.
WorkbookCtx wraps an openpyxl handle + the source path; it's not Pydantic
because it carries the live workbook reference.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.enums.cell_dtype import CellDtype


class Cell(BaseModel):
    model_config = ConfigDict(extra="ignore")
    row: int = Field(ge=1)
    col: int = Field(ge=1)
    address: str
    value: Any = None
    dtype: CellDtype
    in_merge: bool = False
    merge_anchor: str | None = None


class MergedRegion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cell_range: str
    anchor: str
    anchor_value: Any = None


class CellGrid(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sheet: str
    cell_range: str
    cells: list[Cell]


class SheetMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    max_row: int = Field(ge=0)
    max_col: int = Field(ge=0)
    dimensions: str


class WorkbookCtx:
    """Live workbook handle + resolved path. Held in the repository cache."""

    def __init__(self, path: Path, wb):
        self.path = path.resolve()
        self.wb = wb

    def __repr__(self) -> str:
        return f"WorkbookCtx(path={self.path.name})"
