"""Lightweight YAML pipeline loader.

Returns the raw spec dict. The orchestrator wires components into a Haystack
Pipeline using the spec. Kept separate from Haystack-specific construction
so the spec format stays inspectable and hand-editable.
"""
from __future__ import annotations
from pathlib import Path
import yaml


def load_pipeline_yaml(path: Path | str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


class _PassThrough:
    """No-op component used only as a yaml-loader test fixture."""
