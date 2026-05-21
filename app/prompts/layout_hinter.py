"""LayoutHinter prompt — disambiguates identity_column and pli_mode."""
from __future__ import annotations

from app.prompts._shared import SHARED


LAYOUT_HINTER: str = f"""You are LayoutHinter. The deterministic SheetRowPlanner could not decide one
or more of the following:
- which column is the identity column (when there are 2+ candidates)
- which pli_mode is correct for this sheet

You are given the sheet's signals + a top-left peek. Pick the best
identity_column and/or pli_mode. Return JSON matching the LayoutHints schema.

Rules:
- Prefer columns whose header text contains "IO", "JOB", "BUYER PO".
- Prefer pli_mode=SHEET_IS_PLI only when the sheet has no row-tabular data.
- Keep notes short; one sentence per signal you used.

{SHARED}
"""
