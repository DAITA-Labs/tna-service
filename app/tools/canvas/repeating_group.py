"""RepeatingRowGroup detector — rows with identical content signatures.

Reads the `repeating_row_id` channel populated by `build_canvas` (each
distinct repeating group gets a non-zero ID, unique rows get 0) and
emits one `RepeatingRowGroup` per group with its row indices and the
group's content signature string.

A repeating-header pattern is the structural signal for SECTION_PER_PLI
layouts (GUESS, MAIN FALL) — every PLI block is preceded by an identical
header row. The number of group members tells the SectionBoundaryResolver
how many PLI sections to enumerate.
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import RepeatingRowGroup
from app.tools._decorator import tool


@tool("find_repeating_row_groups")
def find_repeating_row_groups(canvas: GridCanvas) -> list[RepeatingRowGroup]:
    """Emit one RepeatingRowGroup per non-zero group id in the channel.

    The channel is populated by `build_canvas` — every row in a group
    carries the same non-zero id across every column; unique rows have
    id 0. We group row indices by id and compute the content signature
    from each group's first row.
    """
    channel = canvas.channels.get("repeating_row_id")
    if channel is None:
        return []

    row_indices_by_id: dict[int, list[int]] = {}
    for r in range(canvas.n_rows):
        # group id is uniform across the row — sample column 0
        gid = channel[r][0] if canvas.n_cols > 0 else 0
        if gid == 0:
            continue
        row_indices_by_id.setdefault(gid, []).append(r + 1)

    groups: list[RepeatingRowGroup] = []
    for gid, rows in sorted(row_indices_by_id.items()):
        signature = _row_signature(canvas, rows[0] - 1)
        groups.append(RepeatingRowGroup(
            row_indices=tuple(rows),
            signature=signature,
        ))
    return groups


def _row_signature(canvas: GridCanvas, row_idx_0based: int) -> str:
    """Build a content signature for a row — joined lowercased stripped cell values."""
    parts: list[str] = []
    for c in range(canvas.n_cols):
        v = canvas.cell_values[row_idx_0based][c]
        if v in (None, ""):
            parts.append("")
        else:
            parts.append(str(v).strip().lower())
    return "\x01".join(parts)
