"""Type-tolerant value comparison for eval scorers.

Scorers compare values across three provenance boundaries:
  - Live-extracted fields (typed: ``date``, ``datetime``, ``int``, ``str``, …)
  - Reloaded frozen outputs (``dict[str, Any]`` metadata keys become ISO strings
    after ``model_dump_json`` → ``model_validate_json`` round-trip)
  - Workbook cells via openpyxl (date/datetime cells always return ``datetime``)
  - Label files loaded via ``_load_label`` (typed fields survive via Pydantic
    validators; ``dict[str, Any]`` fields are bare JSON types)

Using plain ``==`` or ``str()`` equality fails when the same logical value has
different Python types on each side.  This module provides ``values_equal`` as
a single normalisation point.
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Any


def values_equal(a: Any, b: Any) -> bool:
    """Type-tolerant equality for cells, labels, and reloaded ExtractionResults.

    Normalises date / datetime / ISO-8601 string representations to a
    ``date`` before comparing, so that the following are all equal:

    - ``datetime(2026, 5, 15, 0, 0, 0)``  (openpyxl cell, live metadata)
    - ``date(2026, 5, 15)``                (FlexibleDate-parsed field)
    - ``"2026-05-15T00:00:00"``            (metadata after JSON round-trip)
    - ``"2026-05-15 00:00:00"``            (str(datetime))
    - ``"2026-05-15"``                     (str(date) / label string)

    Non-date values fall back to plain equality after stripping trailing
    whitespace on strings.
    """
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return _normalize(a) == _normalize(b)


def _normalize(v: Any) -> Any:
    """Return a canonical form of *v* for comparison.

    ``datetime`` and ``date`` instances are kept as ``date``.  ISO-8601
    strings (with or without time component) are parsed to ``date``.
    Other strings are stripped of surrounding whitespace.  All other
    types are returned unchanged.
    """
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        s = v.strip()
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return s
    return v
