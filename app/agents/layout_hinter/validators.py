"""LayoutHinter semantic validators."""
from __future__ import annotations

import re
from typing import Any

from app.agents._base import OutputVerdict
from app.agents.layout_hinter.schema import LayoutHints


_COL_LETTER_RE = re.compile(r"^[A-Z]+$")
_VALID_PLI_MODES = {"row_per_pli", "section_per_pli", "sheet_is_pli"}


def validate_layout_hints(output: LayoutHints, ctx: Any) -> OutputVerdict:
    """Reject suggestions that aren't well-formed.

    - `identity_column_suggestion` (if present) must be a valid Excel column letter ([A-Z]+).
    - `mode_suggestion` (if present) must be one of the three PliMode enum string values.
    """
    if output.identity_column_suggestion is not None:
        if not _COL_LETTER_RE.match(output.identity_column_suggestion):
            return OutputVerdict.retry(
                reason=f"identity_column_suggestion {output.identity_column_suggestion!r} is not a valid Excel column letter",
            )
    if output.mode_suggestion is not None:
        if output.mode_suggestion not in _VALID_PLI_MODES:
            return OutputVerdict.retry(
                reason=f"mode_suggestion {output.mode_suggestion!r} is not one of {sorted(_VALID_PLI_MODES)}",
            )
    return OutputVerdict.ok()
