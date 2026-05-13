"""Tests for app/repositories/workbook_tools/structure."""
from app.repositories.workbook_repo import register_workbook
from app.repositories.workbook_tools.structure import (
    get_merged_regions, count_non_empty_rows_in_column,
)


def test_get_merged_regions(compass_pro_manos_file):
    ctx = register_workbook(compass_pro_manos_file)
    merges = get_merged_regions(ctx, "Sheet 1")
    # Compass Pro MANOS has 60+ merged regions including header + data merges.
    assert len(merges) > 10


def test_count_non_empty_rows_in_column(dkn_file):
    ctx = register_workbook(dkn_file)
    count = count_non_empty_rows_in_column(ctx, "Sheet 1", "K", row_range=(4, 10))
    # Column K has at least 3 io_numbers in the DKN data rows.
    assert count >= 3
