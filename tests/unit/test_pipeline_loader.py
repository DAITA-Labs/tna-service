"""Tests for app/core/pipeline_loader."""
from app.core.pipeline_loader import load_pipeline_yaml


def test_load_pipeline_yaml_returns_dict(tmp_path):
    yaml_text = """
components:
  a:
    type: app.core.pipeline_loader._PassThrough
connections: []
"""
    p = tmp_path / "pipe.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    spec = load_pipeline_yaml(p)
    assert "components" in spec
    assert "a" in spec["components"]
