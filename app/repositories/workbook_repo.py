"""Workbook I/O — opens xlsx via openpyxl and caches the handle.

`register_workbook(path)` is idempotent: subsequent calls for the same
resolved path return the cached `WorkbookCtx`. Tools and services consume
the context; only this module owns the open handle.
"""
from __future__ import annotations
from pathlib import Path

from openpyxl import load_workbook

from app.models.workbook import WorkbookCtx


_CACHE: dict[Path, WorkbookCtx] = {}


def register_workbook(path: Path | str) -> WorkbookCtx:
    """Open + cache a workbook by absolute path. Idempotent."""
    p = Path(path).resolve()
    if p in _CACHE:
        return _CACHE[p]
    wb = load_workbook(p, data_only=True)
    ctx = WorkbookCtx(p, wb)
    _CACHE[p] = ctx
    return ctx


def clear_cache() -> None:
    """Drop all cached workbooks. Tests should call this between cases."""
    _CACHE.clear()
