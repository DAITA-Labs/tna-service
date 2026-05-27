"""Shared helpers used by multiple field extractors.

Currently:
  `parse_date(value)` — normalise a raw cell value into a `date`, or
  `None` if unparseable.

This module is intentionally lean — helpers land here only when a real
cross-extractor pattern emerges. Per-canonical coercion stays inside
its own extractor file.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any


# ISO: 2026-05-27, 2026/05/27
_ISO_PAT = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")

# Numeric DMY: 27-05-2026, 27/05/2026, 27-05-26, 27/05/26.
# Checked AFTER ISO so a 4-digit year leading still routes to ISO.
_DMY_PAT = re.compile(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{2}|\d{4})$")

# Named-month DMY: 27-May-26, 27 May 2026, 27/May/2026
_NAMED_DMY_PAT = re.compile(r"^(\d{1,2})[\s/-]([A-Za-z]{3,9})[\s/-](\d{2}|\d{4})$")

# Named-month MDY: "May 27, 2026" or "May 27 2026"
_NAMED_MDY_PAT = re.compile(r"^([A-Za-z]{3,9})\s+(\d{1,2})(?:,\s*|\s+)(\d{2}|\d{4})$")

_MONTHS: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}


def parse_date(value: Any) -> dt.date | None:
    """Parse a raw cell value into a date, or None if unparseable.

    Accepted inputs:
      - `datetime.datetime` (openpyxl's typed-cell return) → date()
      - `datetime.date` → returned as-is
      - ISO string: "2026-05-27" or "2026/05/27"
      - Numeric DMY:   "27-05-2026", "27/05/2026", and 2-digit-year variants
                         (matches the TNA-spreadsheet bias toward day-first)
      - Named-month DMY: "27-May-2026", "27 May 26"
      - Named-month MDY: "May 27, 2026", "May 27 2026"
      - blank / non-string non-date → None
    """
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if not isinstance(value, str):
        return None

    s = value.strip()
    if not s:
        return None

    m = _ISO_PAT.match(s)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = _DMY_PAT.match(s)
    if m:
        return _safe_date(
            _expand_year(int(m.group(3))), int(m.group(2)), int(m.group(1)),
        )

    m = _NAMED_DMY_PAT.match(s)
    if m:
        month = _MONTHS.get(m.group(2).lower())
        if month is not None:
            return _safe_date(_expand_year(int(m.group(3))), month, int(m.group(1)))

    m = _NAMED_MDY_PAT.match(s)
    if m:
        month = _MONTHS.get(m.group(1).lower())
        if month is not None:
            return _safe_date(_expand_year(int(m.group(3))), month, int(m.group(2)))

    return None


def _expand_year(y: int) -> int:
    """Expand a 2-digit year to 4-digit (00-69 → 2000-2069; 70-99 → 1970-1999)."""
    if y < 100:
        return 2000 + y if y < 70 else 1900 + y
    return y


def _safe_date(year: int, month: int, day: int) -> dt.date | None:
    """Construct a date, returning None when the components don't form a real date."""
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None
