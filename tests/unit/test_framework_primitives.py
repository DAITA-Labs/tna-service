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


def test_baseprovider_is_abstract_template() -> None:
    """`BaseProvider` is an ABC with abstract primitives and a concrete template."""
    import pytest

    from app.inferencing._base import BaseProvider

    # Cannot instantiate the ABC directly
    with pytest.raises(TypeError):
        BaseProvider()  # type: ignore[abstract]

    # Three abstract primitives + the concrete template
    for name in ("_call_provider", "_record_usage", "_parse_response"):
        assert getattr(BaseProvider, name).__isabstractmethod__, (
            f"{name} must be marked @abstractmethod"
        )
    assert hasattr(BaseProvider, "complete_with_schema")
    assert not getattr(
        BaseProvider.complete_with_schema, "__isabstractmethod__", False,
    ), "complete_with_schema must NOT be abstract (it's the template)"


def test_anthropic_provider_inherits_baseprovider() -> None:
    """`AnthropicProvider` inherits `BaseProvider` and implements the 3 primitives."""
    from app.inferencing._base import BaseProvider
    from app.inferencing.anthropic import AnthropicProvider

    assert issubclass(AnthropicProvider, BaseProvider)
    assert hasattr(AnthropicProvider, "complete_with_schema")
    # `model` is declared on BaseProvider as a typed instance attribute
    assert "model" in BaseProvider.__annotations__
    # Each primitive is overridden (no longer abstract on the concrete class)
    for name in ("_call_provider", "_record_usage", "_parse_response"):
        assert not getattr(
            getattr(AnthropicProvider, name), "__isabstractmethod__", False,
        ), f"AnthropicProvider must override abstract {name}"


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


def test_component_run_unoverridden_raises() -> None:
    """Calling `run` directly on the base raises NotImplementedError."""
    import pytest

    from app.components._base import Component

    class _NoRun(Component):
        pass

    with pytest.raises(NotImplementedError, match="must override run"):
        _NoRun().run(x=1)


def test_component_lifecycle_hooks_default_to_safe_noops() -> None:
    """before_run / after_run are no-ops; on_error logs and does not raise."""
    from haystack import component as hs_component

    from app.components._base import Component

    @hs_component
    class _Probe(Component):
        """Fixture exposing the lifecycle slots so we can poke them."""

        @hs_component.output_types(value=int)
        def run(self, x: int) -> dict:
            return {"value": x}

    probe = _Probe()
    # all three default hooks are callable and return None
    assert probe.before_run({"x": 1}) is None
    assert probe.after_run({"value": 1}) is None
    assert probe.on_error(RuntimeError("boom"), {"x": 1}) is None


def test_component_on_error_is_overridable() -> None:
    """Subclasses can override on_error to record the exception for inspection."""
    from haystack import component as hs_component

    from app.components._base import Component

    captured: list[tuple[str, str, list[str]]] = []

    @hs_component
    class _Recorder(Component):
        """Fixture that captures on_error invocations into a list."""

        @hs_component.output_types(value=int)
        def run(self, x: int) -> dict:
            return {"value": x}

        def on_error(self, exc: Exception, inputs: dict) -> None:
            captured.append((type(exc).__name__, str(exc), sorted(inputs.keys())))

    rec = _Recorder()
    rec.on_error(ValueError("nope"), {"x": 5})
    assert captured == [("ValueError", "nope", ["x"])]


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

    from app.inferencing._base import BaseProvider

    class _FakeProvider(BaseProvider):
        model = "fake"

        def _call_provider(self, *, system, user, output_schema, tool_name):
            return output_schema(v=int(user.strip()))

        def _record_usage(self, *, span, raw, agent_name) -> None:
            pass

        def _parse_response(self, *, raw, tool_name, output_schema):
            return raw

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

    # failure path: provider always raises ValidationError → AgentRunFailure
    class _AlwaysFails(BaseProvider):
        model = "fake"

        def _call_provider(self, **_kw):
            from pydantic import ValidationError
            raise ValidationError.from_exception_data("bad", [])  # type: ignore[arg-type]

        def _record_usage(self, **_kw) -> None:
            pass

        def _parse_response(self, **_kw):
            return None

    failure = _Echo().run(ctx=None, inputs=_Inputs(x=1), provider=_AlwaysFails())
    assert isinstance(failure, AgentRunFailure)
    assert failure.agent_name == "echo_agent"
    assert failure.attempt_count >= 2  # initial + one retry per default policy


def test_make_pipeline_returns_haystack_pipeline_with_components() -> None:
    """`make_pipeline` returns a Haystack Pipeline with the named components added."""
    from haystack import Pipeline, component as hs_component

    from app.components._base import Component
    from app.pipelines._base import make_pipeline

    @hs_component
    class Inc(Component):
        """Add 1 — fixture component."""

        @hs_component.output_types(value=int)
        def run(self, x: int) -> dict:
            return {"value": x + 1}

    pipe = make_pipeline(("incrementer", Inc()))
    assert isinstance(pipe, Pipeline)
    assert "incrementer" in pipe.graph.nodes


def test_shared_prompt_is_importable_string() -> None:
    """`SHARED` exposes the shared prompt header as a non-empty string."""
    from app.prompts._shared import SHARED

    assert isinstance(SHARED, str)
    assert "Glossary" in SHARED
    assert "TNA" in SHARED
    assert "PLI" in SHARED


def test_artifacts_package_reexports_models() -> None:
    """Every artifact class is importable from `app.artifacts` as well as `app.models.artifacts`."""
    import app.artifacts as artifacts
    from app.models import artifacts as legacy

    expected = (
        "SheetPlan",
        "CanonicalNameMap",
        "PlanVerdict",
        "LayoutHints",
        "ValidationFinding",
        "ValidationFindings",
        "HeaderLabel",
        "KVAnchor",
        "StageColumn",
        "StageBandSpec",
        "PliBlock",
        "RowSpec",
        "SheetSignals",
    )
    for cls_name in expected:
        assert hasattr(artifacts, cls_name), f"app.artifacts missing {cls_name!r}"
        assert getattr(artifacts, cls_name) is getattr(legacy, cls_name)


def test_end_to_end_composition_smoke() -> None:
    """Agent + Component + Pipeline + @tool compose without runtime errors."""
    from haystack import component as hs_component
    from pydantic import BaseModel

    from app.agents._base import Agent
    from app.components._base import Component
    from app.inferencing._base import BaseProvider
    from app.pipelines._base import make_pipeline
    from app.pipelines.tuning import Tuning
    from app.tools._decorator import tool
    from app.tools._registry import TOOL_REGISTRY

    @tool("framework_smoke_double")
    def _double(x: int) -> int:
        """Return 2*x — used by the composition smoke agent."""
        return x * 2

    class _Inputs(BaseModel):
        x: int

    class _Out(BaseModel):
        v: int

    class _T(Tuning):
        pass

    class _FakeProvider(BaseProvider):
        model = "fake"

        def _call_provider(self, *, system, user, output_schema, tool_name):
            return output_schema(v=int(user.strip()))

        def _record_usage(self, *, span, raw, agent_name) -> None:
            pass

        def _parse_response(self, *, raw, tool_name, output_schema):
            return raw

    class _SmokeAgent(Agent[_Inputs, _Out]):
        name = "smoke_agent"
        prompt = "Emit the value."
        output_schema = _Out
        tuning = _T()

        def build_input(self, ctx, inputs):
            return str(TOOL_REGISTRY.get("framework_smoke_double")(inputs.x))

    @hs_component
    class _SmokeComponent(Component):
        """Run the smoke agent and surface the parsed `_Out`."""

        @hs_component.output_types(out=_Out)
        def run(self, x: int, provider: object = None) -> dict:
            agent = _SmokeAgent()
            return {"out": agent.run(ctx=None, inputs=_Inputs(x=x), provider=provider or _FakeProvider())}

    pipeline = make_pipeline(("smoke", _SmokeComponent()))
    assert "smoke" in pipeline.graph.nodes
    result = pipeline.run({"smoke": {"x": 7, "provider": _FakeProvider()}})
    assert result["smoke"]["out"].v == 14
