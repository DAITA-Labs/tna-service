"""Importing this package registers all 4 BoundaryPattern handlers."""
from app.services.applier.patterns import (
    one_row_per_pli, data_then_total, vertical_merge, one_sheet_per_pli,
)

__all__ = []
