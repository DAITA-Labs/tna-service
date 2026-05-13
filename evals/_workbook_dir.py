"""Workbook directory resolver.

On systems where symlinks require admin, this module resolves
to the parent dataset directory via pathlib.
"""
from pathlib import Path

# Absolute path to the parent dataset directory (containing workbooks).
WORKBOOKS_DIR = Path("F:/DAITA/ARENA/TNA/dataset").resolve()
