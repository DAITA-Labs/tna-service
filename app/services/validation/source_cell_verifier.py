"""SourceCellVerifier — for each PLI, check the cell at source_cells[field]
still holds the extracted value. Catches drift between extraction and source."""
from __future__ import annotations
from haystack import component
from openpyxl.utils import column_index_from_string
from openpyxl.utils.cell import coordinate_from_string
from app.models.extraction import ExtractionResult
from app.models.artifacts import ValidationFinding, ValidationFindings
from app.models.workbook import WorkbookCtx
from app.enums.validation_severity import ValidationSeverity
from app.core.telemetry import validator_findings_total


def _value_at(ctx: WorkbookCtx, sheet: str, address: str):
    col, row = coordinate_from_string(address)
    return ctx.wb[sheet].cell(row=row, column=column_index_from_string(col)).value


@component
class SourceCellVerifier:
    """Deterministic check — value at source_cells[field] equals PLI.<field>."""

    def __init__(self, workbook_ctx: WorkbookCtx):
        self.ctx = workbook_ctx

    @component.output_types(findings=ValidationFindings)
    def run(self, extraction: ExtractionResult) -> dict:
        findings: list[ValidationFinding] = []
        for i, pli in enumerate(extraction.plis):
            if not pli.source_sheet:
                continue
            for field, addr in pli.source_cells.items():
                try:
                    actual = _value_at(self.ctx, pli.source_sheet, addr)
                except Exception:
                    continue
                extracted = getattr(pli, field, None) or pli.metadata.get(field)
                if extracted is None:
                    continue
                if str(actual) != str(extracted):
                    findings.append(ValidationFinding(
                        check="source_cell",
                        severity=ValidationSeverity.WARN,
                        message=(f"PLI {i} field {field!r}: source {addr!r}={actual!r} "
                                f"!= extracted {extracted!r}"),
                        pli_index=i, field=field,
                    ))
                    validator_findings_total.labels(check="source_cell",
                                                   severity="warn").inc()
        return {"findings": ValidationFindings(findings=findings)}
