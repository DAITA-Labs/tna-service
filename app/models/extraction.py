"""Output contract — PLI, Stage, ExtractionResult, Warning.

Aligned with the user's hand-labeled ground truth in dataset/extracted/*.json.
extra="ignore" everywhere so envelope additions stay backward-compatible.
FlexibleDate handles supplier-specific formats (DD-MMM-YYYY, DD/MM/YYYY, etc).

`PLI.source` and `Stage.source` are nested traceability (sheet/rows/cells):
`source.cells` maps each canonical field / metadata key to the A1 address its
value was read from. Lets a reviewer open the workbook and verify any extracted
value at its source. Also drives the SourceCellVerifier validator.
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Annotated, Any, Literal
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator


_DATE_FORMATS_TO_TRY = (
    "%d-%b-%Y", "%d-%b-%y", "%d %b %Y",
    "%d/%m/%Y", "%d/%m/%y",
    "%d.%m.%Y", "%d-%m-%Y",
)


def _parse_flexible_date(value: Any) -> Any:
    """Coerce supplier date formats to date; pass through unknown values."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return value
    s = value.strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS_TO_TRY:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return value


FlexibleDate = Annotated[date | None, BeforeValidator(_parse_flexible_date)]


class Source(BaseModel):
    """Per-field traceability — which sheet/row/cell each value was read from.

    Shared by `PLI.source` and `Stage.source` so any extracted value can be
    verified by opening the source workbook at `source.sheet` + `source.cells[field]`.
    """
    model_config = ConfigDict(extra="ignore")
    sheet: str | None = None
    rows: list[int] = Field(default_factory=list)
    cells: dict[str, str] = Field(default_factory=dict)


class Stage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    planned_date: FlexibleDate = None
    quantity: int | None = None
    section: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    # Per-stage traceability: source.sheet, source.rows (the row(s) this stage
    # was read from on its parent PLI), source.cells maps "planned_date" +
    # each Stage.metadata key to its A1 address.
    source: Source = Field(default_factory=Source)


class PLI(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _drop_none_confidence_values(cls, values):
        if isinstance(values, dict):
            conf = values.get("confidence")
            if isinstance(conf, dict):
                cleaned = {k: v for k, v in conf.items() if v is not None}
                if len(cleaned) != len(conf):
                    values = dict(values)
                    values["confidence"] = cleaned
        return values

    io_number: str | None = None
    style_code: str | None = None
    style_name: str | None = None
    color_code: str | None = None
    color_name: str | None = None
    fabric_code: str | None = None
    delivery_date: FlexibleDate = None
    quantity: int | None = None
    stages: list[Stage] = Field(default_factory=list)
    confidence: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Single nested traceability: source.sheet, source.rows, source.cells.
    # `source.cells` maps every canonical field + every metadata key to its
    # A1 origin (e.g. {"io_number": "K4", "delivery_date": "P4"}).
    source: Source = Field(default_factory=Source)


class Warning(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: str
    severity: Literal["info", "warning", "error"] = "warning"
    pli_index: int | None = None
    field: str | None = None
    check: str | None = None


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _coerce_string_warnings(cls, values):
        if isinstance(values, dict):
            raw = values.get("warnings")
            if isinstance(raw, list):
                values = dict(values)
                values["warnings"] = [
                    {"message": w} if isinstance(w, str) else w for w in raw
                ]
        return values

    plis: list[PLI] = Field(default_factory=list)
    warnings: list[Warning] = Field(default_factory=list)
    format_detected: str | None = None
    extraction_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source_file: str | None = None
