"""Unit tests proving the new framework primitive packages exist and import cleanly."""
from __future__ import annotations

import importlib


def test_new_packages_import() -> None:
    """Every new framework package must be importable."""
    for module_name in (
        "app.pipelines",
        "app.components",
        "app.agents",
        "app.inferencing",
        "app.tools",
        "app.artifacts",
    ):
        importlib.import_module(module_name)


def test_provider_is_runtime_checkable_protocol() -> None:
    """`Provider` must be a runtime-checkable Protocol with `complete_with_schema`."""
    from typing import get_type_hints

    from app.inferencing._base import Provider

    assert hasattr(Provider, "complete_with_schema")
    # runtime_checkable Protocols expose this attribute
    assert getattr(Provider, "_is_runtime_protocol", False) is True
    hints = get_type_hints(Provider.complete_with_schema)
    for required in ("system", "user", "output_schema", "tool_name", "agent_name"):
        assert required in hints, f"Provider.complete_with_schema missing kw {required!r}"


def test_anthropic_provider_satisfies_protocol() -> None:
    """The new AnthropicProvider class must satisfy the Provider Protocol."""
    from app.inferencing._base import Provider
    from app.inferencing.anthropic import AnthropicProvider

    # class-level structural check
    assert hasattr(AnthropicProvider, "complete_with_schema")

    # isinstance against a fake instance: build the minimum needed object
    class _Fake(AnthropicProvider):
        def __init__(self) -> None:
            self.model = "fake"

    fake = _Fake()
    assert hasattr(fake, "model")
    assert isinstance(fake, Provider)


def test_pipeline_tuning_loads_defaults() -> None:
    """`PipelineTuning()` instantiates with documented defaults."""
    from app.pipelines.tuning import PipelineTuning, Tuning

    pt = PipelineTuning()
    assert pt.extract_confidence_gate == 0.85
    assert pt.coverage_floor == 0.80
    assert pt.dropout_floor == 0.50
    # subclass relationship lets agent tuning classes inherit later
    assert issubclass(PipelineTuning, Tuning)
