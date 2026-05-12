"""Tests for app/repositories/workbook_tools/search."""
from app.repositories.workbook_repo import register_workbook
from app.repositories.workbook_tools.search import find_value


def test_find_value_returns_addresses(dkn_file):
    ctx = register_workbook(dkn_file)
    hits = find_value(ctx, "Sheet 1", "Buyer Po No", max_hits=5)
    assert len(hits) >= 1
