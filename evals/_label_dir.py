"""Label directory resolver.

On systems where symlinks require admin, this module resolves
to the extracted labels directory via pathlib.
"""
from pathlib import Path

# Absolute path to the parent dataset extracted labels directory.
LABELS_DIR = Path("F:/DAITA/ARENA/TNA/dataset/extracted").resolve()
