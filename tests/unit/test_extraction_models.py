"""Tests for app/models/extraction — FlexibleDate + PLI + ExtractionResult."""
from datetime import date, datetime
from app.models.extraction import (
    PLI, Stage, ExtractionResult, Warning, _parse_flexible_date,
)


def test_flexible_date_dd_mmm_yyyy():
    assert _parse_flexible_date("19-MAY-2026") == date(2026, 5, 19)


def test_flexible_date_dd_slash_mm_yyyy():
    assert _parse_flexible_date("07/04/2026") == date(2026, 4, 7)


def test_flexible_date_datetime_passthrough():
    assert _parse_flexible_date(datetime(2026, 3, 25)) == date(2026, 3, 25)


def test_flexible_date_none_passthrough():
    assert _parse_flexible_date(None) is None


def test_pli_delivery_date_coerces():
    p = PLI(io_number="7000022459", delivery_date="19-MAY-2026")
    assert p.delivery_date == date(2026, 5, 19)


def test_pli_source_nested():
    p = PLI(io_number="1", source={"sheet": "Sheet", "rows": [4],
                                   "cells": {"io_number": "K4"}})
    assert p.source.sheet == "Sheet"
    assert p.source.rows == [4]
    assert p.source.cells["io_number"] == "K4"


def test_stage_planned_date_coerces():
    s = Stage(name="Sewing", planned_date="23-APR-2026")
    assert s.planned_date == date(2026, 4, 23)


def test_extraction_result_warnings_coerce_strings():
    e = ExtractionResult(plis=[], warnings=["heads up"])
    assert isinstance(e.warnings[0], Warning)
    assert e.warnings[0].message == "heads up"
