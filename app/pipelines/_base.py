"""Pipeline factory helper — composes Haystack `Pipeline` from named Components."""
from __future__ import annotations

from haystack import Pipeline

from app.components._base import Component


def make_pipeline(*components: tuple[str, Component]) -> Pipeline:
    """Return a Haystack Pipeline with each `(name, component)` pair added.

    Edge wiring (`pipeline.connect`) is intentionally left to the caller —
    concrete pipeline factories (e.g. `make_extract_pipeline`) own the
    topology.
    """
    pipeline = Pipeline()
    for name, comp in components:
        pipeline.add_component(name, comp)
    return pipeline
