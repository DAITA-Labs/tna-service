"""parse_date — shared date-parsing helper for field extractors."""
from __future__ import annotations

import datetime as dt

from app.components.field._helpers import parse_date


def test_datetime_input_returns_its_date_part() -> None:
    assert parse_date(dt.datetime(2026, 5, 27, 14, 30)) == dt.date(2026, 5, 27)


def test_date_input_returned_as_is() -> None:
    d = dt.date(2026, 5, 27)
    assert parse_date(d) is d


def test_iso_format_dash() -> None:
    assert parse_date("2026-05-27") == dt.date(2026, 5, 27)


def test_iso_format_slash() -> None:
    assert parse_date("2026/05/27") == dt.date(2026, 5, 27)


def test_dmy_numeric_dash_4_digit_year() -> None:
    assert parse_date("27-05-2026") == dt.date(2026, 5, 27)


def test_dmy_numeric_slash_4_digit_year() -> None:
    assert parse_date("27/05/2026") == dt.date(2026, 5, 27)


def test_dmy_numeric_2_digit_year_recent() -> None:
    """2-digit year 00-69 → 2000-2069 (TNA orders skew recent)."""
    assert parse_date("27/05/26") == dt.date(2026, 5, 27)


def test_dmy_numeric_2_digit_year_legacy() -> None:
    """2-digit year 70-99 → 1970-1999."""
    assert parse_date("27/05/85") == dt.date(1985, 5, 27)


def test_named_dmy_dash() -> None:
    assert parse_date("27-May-2026") == dt.date(2026, 5, 27)


def test_named_dmy_space() -> None:
    assert parse_date("27 May 2026") == dt.date(2026, 5, 27)


def test_named_dmy_full_month_name() -> None:
    assert parse_date("27 September 2026") == dt.date(2026, 9, 27)


def test_named_mdy_with_comma() -> None:
    assert parse_date("May 27, 2026") == dt.date(2026, 5, 27)


def test_named_mdy_without_comma() -> None:
    assert parse_date("May 27 2026") == dt.date(2026, 5, 27)


def test_invalid_components_return_none() -> None:
    """Day 32 / month 13 / Feb 30 reject cleanly via the date constructor."""
    assert parse_date("32-05-2026") is None
    assert parse_date("27-13-2026") is None
    assert parse_date("30-02-2026") is None


def test_garbage_string_returns_none() -> None:
    assert parse_date("TBD") is None
    assert parse_date("not a date") is None


def test_empty_or_whitespace_returns_none() -> None:
    assert parse_date("") is None
    assert parse_date("   ") is None


def test_none_input_returns_none() -> None:
    assert parse_date(None) is None


def test_non_date_non_string_returns_none() -> None:
    """Ints / floats not interpreted as Excel serials by this helper."""
    assert parse_date(45000) is None
    assert parse_date(45000.0) is None


def test_unknown_month_name_rejected() -> None:
    """Unrecognised month text falls through to None."""
    assert parse_date("27-Maybe-2026") is None
