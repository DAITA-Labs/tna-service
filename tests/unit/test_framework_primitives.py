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


def test_tool_decorator_registers_callable() -> None:
    """`@tool('name')` registers a function and `TOOL_REGISTRY.get(name)` returns it."""
    from app.tools._decorator import tool
    from app.tools._registry import TOOL_REGISTRY

    @tool("framework_test_echo")
    def echo(x: int) -> int:
        """Return x — fixture for registry test."""
        return x

    # decorated function is callable directly
    assert echo(7) == 7

    # and the registry has an instrumented entry under the name
    registered = TOOL_REGISTRY.get("framework_test_echo")
    assert callable(registered)
    assert registered(9) == 9

    # double registration is rejected
    import pytest

    with pytest.raises(ValueError):
        @tool("framework_test_echo")
        def _dupe(x: int) -> int:
            return x


def test_component_base_runs_under_haystack() -> None:
    """A subclass of `Component` decorated with `@component` runs and produces typed output."""
    from haystack import component as hs_component

    from app.components._base import Component

    @hs_component
    class Doubler(Component):
        """Return x doubled — fixture component."""

        @hs_component.output_types(value=int)
        def run(self, x: int) -> dict:
            return {"value": x * 2}

    out = Doubler().run(x=4)
    assert out == {"value": 8}


def test_agent_base_runs_and_lifecycle_hooks_are_noops() -> None:
    """`Agent` is generic, calls the provider, and the default hooks return without error."""
    from typing import Generic, get_type_hints

    from pydantic import BaseModel

    from app.agents._base import Agent, AgentRunFailure, RetryPolicy
    from app.pipelines.tuning import Tuning

    class _Out(BaseModel):
        v: int

    class _Inputs(BaseModel):
        x: int

    class _T(Tuning):
        pass

    class _FakeProvider:
        model = "fake"

        def complete_with_schema(self, *, system, user, output_schema, tool_name, agent_name):
            return output_schema(v=int(user.strip()))

    class _Echo(Agent[_Inputs, _Out]):
        name = "echo_agent"
        prompt = "You echo numbers."
        output_schema = _Out
        tuning = _T()

        def build_input(self, ctx, inputs):
            return str(inputs.x)

    # generic params survive subclassing
    assert any(getattr(b, "__origin__", None) is Agent for b in _Echo.__orig_bases__)

    out = _Echo().run(ctx=None, inputs=_Inputs(x=42), provider=_FakeProvider())
    assert isinstance(out, _Out) and out.v == 42

    # retry policy is a frozen dataclass with max_retries=1
    rp = RetryPolicy()
    assert rp.max_retries == 1

    # failure path: provider always raises ValueError → AgentRunFailure
    class _AlwaysFails:
        model = "fake"

        def complete_with_schema(self, **_kw):
            from pydantic import ValidationError
            raise ValidationError.from_exception_data("bad", [])  # type: ignore[arg-type]

    failure = _Echo().run(ctx=None, inputs=_Inputs(x=1), provider=_AlwaysFails())
    assert isinstance(failure, AgentRunFailure)
    assert failure.agent_name == "echo_agent"
    assert failure.attempt_count >= 2  # initial + one retry per default policy
