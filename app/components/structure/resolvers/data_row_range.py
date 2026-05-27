"""DataRowRangeResolver — find contiguous PLI data row ranges under a HeaderBand.

A DataRowRange starts on the first row after `bag.header_band.rect.r1`
and continues until one of:
  - 2+ consecutive empty rows
  - the sheet's last row
  - a "Total" / "Subtotal" / "Grand Total" indicator row (filtered)

Most tabular sheets have one DataRowRange. SECTION_PER_PLI sheets (GUESS,
MAIN FALL) may have multiple ranges separated by section headers; this
resolver still emits one range per contiguous block — SectionBoundaryResolver
handles section enumeration separately.
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import DataRowRange, StructureBag


_MAX_CONSECUTIVE_BLANK = 2
_TOTAL_PREFIXES = ("total", "subtotal", "grand total", "grand-total")


def resolve_data_row_ranges(canvas: GridCanvas, bag: StructureBag) -> list[DataRowRange]:
    """Emit one DataRowRange per contiguous block of PLI data rows.

    Requires `bag.header_band` to be populated. Emits an empty list and
    leaves `bag.data_row_ranges` empty when no header exists.
    """
    if bag.header_band is None:
        bag.data_row_ranges = []
        return []

    empty_row_channel = canvas.channels.get("empty_row", [])
    first_data_row_0idx = bag.header_band.rect.r1  # 1-indexed r1 → 0-indexed start

    ranges: list[DataRowRange] = []
    current_start: int | None = None
    consecutive_blank = 0

    for r in range(first_data_row_0idx, canvas.n_rows):
        is_empty = _row_is_empty(empty_row_channel, r)
        is_total = _row_is_total(canvas, r)

        if is_total:
            # Total row terminates the current range without entering it.
            if current_start is not None:
                ranges.append(DataRowRange(row_start=current_start + 1, row_end=r))
                current_start = None
                consecutive_blank = 0
            continue

        if is_empty:
            consecutive_blank += 1
            if consecutive_blank >= _MAX_CONSECUTIVE_BLANK and current_start is not None:
                # Close the current range BEFORE the blank run.
                ranges.append(DataRowRange(
                    row_start=current_start + 1,
                    row_end=r - consecutive_blank + 1,
                ))
                current_start = None
            continue

        # Non-empty, non-total row.
        consecutive_blank = 0
        if current_start is None:
            current_start = r

    if current_start is not None:
        ranges.append(DataRowRange(row_start=current_start + 1, row_end=canvas.n_rows))

    bag.data_row_ranges = ranges
    return ranges


def _row_is_empty(empty_row_channel: list[list[int]], r: int) -> bool:
    """Check the empty_row channel — 1 means the whole row is blank."""
    if r >= len(empty_row_channel):
        return False
    row = empty_row_channel[r]
    return len(row) > 0 and row[0] == 1


def _row_is_total(canvas: GridCanvas, r: int) -> bool:
    """Detect 'Total' / 'Subtotal' / 'Grand Total' rows by leading-cell text."""
    if r >= canvas.n_rows:
        return False
    for c in range(min(canvas.n_cols, 4)):
        value = canvas.cell_values[r][c]
        if isinstance(value, str):
            text = value.strip().lower()
            if any(text.startswith(prefix) for prefix in _TOTAL_PREFIXES):
                return True
    return False
