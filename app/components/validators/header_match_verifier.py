"""HeaderMatchVerifier — for each canonical-field's source column, the header
row should contain text related to the canonical vocabulary."""
from __future__ import annotations

from haystack import component
from openpyxl.utils import column_index_from_string
from openpyxl.utils.cell import coordinate_from_string

from app.core.logs import get_logger
from app.core.telemetry import validator_findings_total
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import ValidationFinding, ValidationFindings
from app.models.extraction import ExtractionResult
from app.models.workbook import WorkbookCtx

log = get_logger(__name__)


_VOCAB = {
    "io_number": ("po", "buyer", "io", "job", "order ref", "order number", "order no"),
    "style_code": ("style",),
    "color_code": ("color", "colour"),
    "fabric_code": ("fabric", "material", "quality"),
    "delivery_date": ("delivery", "ex factory", "ex-fac", "ex fac", "etd", "ship"),
    "quantity": ("qty", "quantity", "order qty", "plan qty"),
}


@component
class HeaderMatchVerifier:
    """Validates that each PLI field's source column has a recognisable header; emits a finding when no vocab term matches."""

    def __init__(self, workbook_ctx: WorkbookCtx):
        self.ctx = workbook_ctx

    @component.output_types(findings=ValidationFindings)
    def run(self, extraction: ExtractionResult) -> dict:
        """Check header text against vocabulary for each sourced field and return findings keyed by 'findings'."""
        findings: list[ValidationFinding] = []
        seen: set[tuple] = set()
        for i, pli in enumerate(extraction.plis):
            for field, addr in pli.source.cells.items():
                if field not in _VOCAB or not pli.source.sheet:
                    continue
                col, _ = coordinate_from_string(addr)
                key = (pli.source.sheet, col, field)
                if key in seen:
                    continue
                seen.add(key)
                ws = self.ctx.wb[pli.source.sheet]
                col_idx = column_index_from_string(col)
                header_text = " ".join(
                    str(ws.cell(row=r, column=col_idx).value or "").lower()
                    for r in range(1, min(6, (ws.max_row or 1) + 1))
                )
                vocab = _VOCAB[field]
                if not any(term in header_text for term in vocab):
                    log.warning("header_match_warn", field=field, col=col,
                                header=header_text[:40])
                    findings.append(ValidationFinding(
                        check="header_match",
                        severity=ValidationSeverity.WARN,
                        message=(f"field {field!r} sourced from column {col} "
                                f"but header text {header_text!r} contains none of {vocab}"),
                        pli_index=i, field=field,
                    ))
                    validator_findings_total.add(
                        1, {"check": "header_match", "severity": "warn"}
                    )
        return {"findings": ValidationFindings(findings=findings)}
