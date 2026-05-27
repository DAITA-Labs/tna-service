"""Base canonical component — per-canonical extraction over a ClusterAnchorBundle.

Concrete subclasses set a single class-level `canonical` attribute and
optionally override `_postprocess` to coerce raw cell values into the
canonical's value space. Layout-specific extraction is dispatched on
`bundle.hint.axes.pli_axis`.

Currently supported axes:

  vertical   — tabular ROW_PER_PLI. One Finding per data row whose
                candidate column carries a non-blank value. Implemented.

  sectional  — SECTION_PER_PLI. Deferred.
  sheet      — SHEET_IS_PLI. Deferred.
  horizontal — column-per-PLI. Deferred.

`extract_findings(bundle)` returns an empty list for unsupported axes
so a workbook with mixed templates degrades gracefully rather than
raising.
"""
from __future__ import annotations

from typing import Any

from openpyxl.utils import get_column_letter

from app.artifacts.finding import Confidence, Coord, Finding
from app.artifacts.workbook import ClusterAnchorBundle


class BaseCanonicalComponent:
    """Abstract base for every per-canonical field component.

    Subclasses MUST override `canonical` (a class-level str matching one of
    the identifier-spec canonicals). They MAY override `_postprocess` to
    coerce raw cell values.
    """

    canonical: str = ""

    def extract_findings(self, bundle: ClusterAnchorBundle) -> list[Finding]:
        """Extract one Finding per occurrence of this canonical in the bundle."""
        if not self.canonical:
            raise NotImplementedError(
                f"{type(self).__name__} must set a `canonical` class attribute."
            )
        axis = bundle.hint.axes.pli_axis
        if axis == "vertical":
            return self._extract_row_per_pli(bundle)
        return []

    def _extract_row_per_pli(self, bundle: ClusterAnchorBundle) -> list[Finding]:
        """ROW_PER_PLI extraction — one Finding per data row in the canonical's column."""
        columns = bundle.hint.candidate_columns.get(self.canonical, [])
        rows = bundle.hint.candidate_rows.get(self.canonical, [])
        if not columns or not rows:
            return []

        col_idx = columns[0]  # arbitration of multi-column candidates deferred
        col_letter = get_column_letter(col_idx)
        label_coord = self._label_coord_for(bundle, col_letter)

        findings: list[Finding] = []
        for row in rows:
            raw = bundle.canvas.cell_values[row - 1][col_idx - 1]
            if raw is None or raw == "":
                continue
            findings.append(Finding(
                canonical=self.canonical,
                label_coord=label_coord,
                value_coord=(col_letter, row),
                value=self._postprocess(raw),
                confidence=Confidence.MEDIUM,
                evidence=["HEADER_BAND_MEMBER", "DTYPE_MATCH"],
            ))
        return findings

    def _label_coord_for(self, bundle: ClusterAnchorBundle, col_letter: str) -> Coord:
        """Return the header-band cell coord for the canonical's column."""
        band = bundle.hint.header_band
        if band is None:
            return (col_letter, 1)
        return (col_letter, band.rect.r0)

    def _postprocess(self, value: Any) -> Any:
        """Coerce a raw cell value into the canonical's value space.

        Default: identity. Subclasses override for type coercion (e.g.,
        io_number normalises numeric io-codes back to strings).
        """
        return value
