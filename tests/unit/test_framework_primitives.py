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
