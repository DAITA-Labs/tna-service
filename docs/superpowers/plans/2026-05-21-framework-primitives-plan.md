# Framework Primitives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the new framework primitives (directories + base classes) so subsequent sub-plans can migrate existing code onto them. Nothing user-visible changes.

**Architecture:** Seven primitives per spec §3. Adopt Haystack `Pipeline` + `@component` + `OpenTelemetryTracer` as the substrate. Add a custom `Agent[Inputs, Output]` base (NOT Haystack's ReAct Agent) with lifecycle-hook slots defaulting to no-ops. Add `Provider` Protocol, `@tool` decorator + registry, `Tuning` base, `Component` base wrapping Haystack.

**Tech Stack:** Python 3.12, Haystack 2.10+, Pydantic 2.6+, pydantic-settings, structlog, OpenTelemetry SDK 1.27+.

---

## Conventions (engineer: read once, apply to every task)

- Python 3.12+, modern types (`list[X]`, `X | None`, no `Optional`/`List`/`Dict`/`Union` from `typing`).
- `from __future__ import annotations` at the top of every new file (codebase convention).
- One-line imperative docstring on every public function, class, and module.
- Function bodies ≤ 40 lines (CODING_STANDARD §2); split with named helpers if longer.
- No narrative comments — only constraint / workaround / external-reference comments.
- Conventional commits (`feat:`, `chore:`, `refactor:`, `test:`).
- After every commit, `make test` must pass (`pytest -q -m "not live"`).
- No existing file under `app/services/`, `app/repositories/`, `app/prompts/workflow/` is touched in this plan. Existing imports keep working.
- Tests live under `tests/unit/` for this sub-plan. No live tests are added.
- All paths absolute from repo root.

---

## Task overview

| # | Task | Type |
|---|---|---|
| 1 | Create empty package skeleton (directories + `__init__.py`) | chore |
| 2 | Add `app/inferencing/_base.py` Provider Protocol | feat |
| 3 | Add `app/inferencing/anthropic.py` copy of AnthropicProvider | feat |
| 4 | Add `app/pipelines/tuning.py` PipelineTuning settings + base `Tuning` | feat |
| 5 | Add `app/tools/_registry.py` + `app/tools/_decorator.py` (new registry) | feat |
| 6 | Add `app/components/_base.py` Component base (Haystack `@component`) | feat |
| 7 | Add `app/agents/_base.py` Agent generic base with lifecycle no-op hooks | feat |
| 8 | Add `app/pipelines/_base.py` `make_pipeline` helper | feat |
| 9 | Add `app/prompts/_shared.py` SHARED constant | feat |
| 10 | Wire `app/artifacts/__init__.py` re-exports from `app.models.artifacts` | feat |
| 11 | Add integration test asserting types compose end-to-end | test |

---

## Task 1 — Create the empty package skeleton

**Files:**
- Create: `app/pipelines/__init__.py`
- Create: `app/components/__init__.py`
- Create: `app/agents/__init__.py`
- Create: `app/inferencing/__init__.py`
- Create: `app/tools/__init__.py`
- Create: `app/artifacts/__init__.py`
- Modify: (none yet)
- Test: `tests/unit/test_framework_primitives.py`

Note: `app/prompts/__init__.py` already exists. It is NOT touched in this task — the existing content stays intact. Sub-plan 4 will replace it.

- [ ] **1.1 Write the failing test.**

Create `tests/unit/test_framework_primitives.py` with this content:

```python
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
```

- [ ] **1.2 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py -q
```

Expected: failure — `ModuleNotFoundError: No module named 'app.pipelines'` (or the first new package alphabetically).

- [ ] **1.3 Write minimal implementation.**

Create each `__init__.py` with only a module docstring. Exact contents:

`app/pipelines/__init__.py`:
```python
"""Pipeline primitives — top-level orchestration package."""
```

`app/components/__init__.py`:
```python
"""Component primitives — deterministic + LLM-backed pipeline units."""
```

`app/agents/__init__.py`:
```python
"""Agent primitives — one narrow LLM mapping job per agent."""
```

`app/inferencing/__init__.py`:
```python
"""Inferencing primitives — single LLM provider boundary."""
```

`app/tools/__init__.py`:
```python
"""Tool primitives — deterministic side-effect-free helpers, `@tool`-decorated."""
```

`app/artifacts/__init__.py`:
```python
"""Artifact primitives — re-exports of pipeline-shared Pydantic models."""
```

- [ ] **1.4 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py -q
```

Expected: `1 passed`. Then run the full suite:

```bash
make test
```

Expected: full suite still green (252 passing pre-existing + 1 new).

- [ ] **1.5 Commit.**

```bash
git add app/pipelines/__init__.py app/components/__init__.py app/agents/__init__.py \
        app/inferencing/__init__.py app/tools/__init__.py app/artifacts/__init__.py \
        tests/unit/test_framework_primitives.py
git commit -m "$(cat <<'EOF'
chore(framework): scaffold empty primitive packages

Adds app/pipelines, app/components, app/agents, app/inferencing,
app/tools, app/artifacts with module docstrings only. No code moves;
existing app/services/* still serves the API.
EOF
)"
```

---

## Task 2 — Provider Protocol in `app/inferencing/_base.py`

**Files:**
- Create: `app/inferencing/_base.py`
- Test: `tests/unit/test_framework_primitives.py` (extend)

- [ ] **2.1 Write the failing test.**

Append to `tests/unit/test_framework_primitives.py`:

```python
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
```

- [ ] **2.2 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py::test_provider_is_runtime_checkable_protocol -q
```

Expected: `ModuleNotFoundError: No module named 'app.inferencing._base'`.

- [ ] **2.3 Write minimal implementation.**

Create `app/inferencing/_base.py`:

```python
"""Provider protocol — the single surface every inferencing backend implements."""
from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class Provider(Protocol):
    """Interface for an LLM provider that returns a schema-validated Pydantic model."""

    model: str

    def complete_with_schema(
        self,
        *,
        system: str,
        user: str,
        output_schema: type[T],
        tool_name: str,
        agent_name: str = "unknown",
    ) -> T: ...
```

- [ ] **2.4 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py -q
```

Expected: all tests pass. Run `make test`; full suite green.

- [ ] **2.5 Commit.**

```bash
git add app/inferencing/_base.py tests/unit/test_framework_primitives.py
git commit -m "$(cat <<'EOF'
feat(inferencing): add Provider Protocol base

Defines the single surface (`complete_with_schema`) every LLM backend
must implement. Runtime-checkable so isinstance() works in tests.
EOF
)"
```

---

## Task 3 — AnthropicProvider copy in `app/inferencing/anthropic.py`

The new file is a verbatim copy of `app/services/llm_provider.py` minus the `LLMProvider` Protocol (which lives in `_base.py` now as `Provider`). The class implements the new `Provider` Protocol. The old file stays put so existing imports keep working.

**Files:**
- Create: `app/inferencing/anthropic.py`
- Test: `tests/unit/test_framework_primitives.py` (extend)

- [ ] **3.1 Write the failing test.**

Append to `tests/unit/test_framework_primitives.py`:

```python
def test_anthropic_provider_satisfies_protocol() -> None:
    """The new AnthropicProvider class must satisfy the Provider Protocol."""
    from app.inferencing._base import Provider
    from app.inferencing.anthropic import AnthropicProvider

    # class-level structural check
    assert hasattr(AnthropicProvider, "complete_with_schema")
    assert hasattr(AnthropicProvider, "model")

    # isinstance against a fake instance: build the minimum needed object
    class _Fake(AnthropicProvider):
        def __init__(self) -> None:
            self.model = "fake"

    assert isinstance(_Fake(), Provider)
```

- [ ] **3.2 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py::test_anthropic_provider_satisfies_protocol -q
```

Expected: `ModuleNotFoundError: No module named 'app.inferencing.anthropic'`.

- [ ] **3.3 Write minimal implementation.**

Create `app/inferencing/anthropic.py`:

```python
"""Anthropic SDK wrapper — drives schema-constrained tool-use completions."""
from __future__ import annotations

import time

from anthropic import Anthropic
from pydantic import BaseModel

from app.config.settings import get_settings
from app.core.logs import get_logger
from app.core.telemetry import (
    agent_tokens_input,
    agent_tokens_output,
    llm_calls_total,
    llm_inference_duration_seconds,
)
from app.core.tracing import get_tracer
from app.inferencing._base import T


log = get_logger(__name__)


class MissingAPIKey(RuntimeError):
    """Raised when ANTHROPIC_API_KEY is not set."""


def _inline_refs(schema: dict, defs: dict | None = None) -> dict:
    """Recursively replace `{"$ref": "#/$defs/X"}` entries with the actual schema X.

    Anthropic tool-use otherwise emits nested objects as JSON-encoded strings,
    which Pydantic then rejects.
    """
    if defs is None:
        defs = schema.get("$defs", {}) or schema.get("definitions", {}) or {}

    if isinstance(schema, dict):
        if "$ref" in schema and len(schema) == 1:
            ref = schema["$ref"]
            assert ref.startswith("#/$defs/") or ref.startswith("#/definitions/"), \
                f"unexpected $ref {ref!r}"
            name = ref.rsplit("/", 1)[-1]
            return _inline_refs(defs[name], defs)
        return {
            k: _inline_refs(v, defs)
            for k, v in schema.items()
            if k not in ("$defs", "definitions")
        }
    if isinstance(schema, list):
        return [_inline_refs(v, defs) for v in schema]
    return schema


def schema_to_tool(name: str, model: type[BaseModel]) -> dict:
    """Build an Anthropic tool definition that emits a Pydantic schema."""
    raw = model.model_json_schema()
    inlined = _inline_refs(raw)
    return {
        "name": name,
        "description": f"Emit a structured {model.__name__} result.",
        "input_schema": inlined,
    }


class AnthropicProvider:
    """Anthropic SDK wrapper that drives schema-constrained tool-use completions."""

    def __init__(self, client: Anthropic, model: str,
                 max_tokens: int = 4096, temperature: float = 0.0):
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    @classmethod
    def from_env(cls, api_key: str | None = None) -> "AnthropicProvider":
        """Construct an AnthropicProvider from environment settings."""
        s = get_settings()
        key = api_key or s.anthropic_api_key
        if not key:
            raise MissingAPIKey(
                "ANTHROPIC_API_KEY is not set. Add it to .env (see .env.example)."
            )
        client = Anthropic(api_key=key)
        return cls(
            client=client, model=s.anthropic_model,
            max_tokens=s.max_tokens, temperature=s.temperature,
        )

    def complete_with_schema(
        self, *, system: str, user: str,
        output_schema: type[T], tool_name: str,
        agent_name: str = "unknown",
    ) -> T:
        """Call the Anthropic API and parse the response into output_schema."""
        tool = schema_to_tool(tool_name, output_schema)
        log.debug("llm_call_start", model=self.model, tool=tool_name,
                  system_chars=len(system), user_chars=len(user))
        t0 = time.monotonic()
        with get_tracer(__name__).start_as_current_span("llm.complete") as span:
            span.set_attribute("llm.model", self.model)
            span.set_attribute("llm.agent", agent_name)
            resp = self._call_sdk(system=system, user=user, tool=tool, tool_name=tool_name)
            llm_inference_duration_seconds.record(
                time.monotonic() - t0, {"model": self.model}
            )
            llm_calls_total.add(1, {"model": self.model, "status": "success"})
            self._record_usage(span=span, resp=resp, agent_name=agent_name)
            return self._parse_tool_response(
                resp=resp, tool_name=tool_name, output_schema=output_schema,
            )

    def _call_sdk(self, *, system: str, user: str, tool: dict, tool_name: str):
        """Submit the completion request to the Anthropic API.

        Records a failure counter and re-raises on any SDK error.
        """
        try:
            return self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
            )
        except Exception:
            llm_calls_total.add(1, {"model": self.model, "status": "failure"})
            raise

    def _record_usage(self, *, span, resp, agent_name: str) -> None:
        """Emit token-count metrics and span attributes from the response usage block."""
        usage = getattr(resp, "usage", None)
        inp_tokens: int | None = None
        out_tokens: int | None = None
        if usage is not None:
            inp_tokens = getattr(usage, "input_tokens", None)
            out_tokens = getattr(usage, "output_tokens", None)
            if isinstance(inp_tokens, int):
                agent_tokens_input.add(
                    inp_tokens, {"agent": agent_name, "model": self.model}
                )
                span.set_attribute("llm.input_tokens", inp_tokens)
            if isinstance(out_tokens, int):
                agent_tokens_output.add(
                    out_tokens, {"agent": agent_name, "model": self.model}
                )
                span.set_attribute("llm.output_tokens", out_tokens)
        log.info("llm_call_complete", model=self.model, agent=agent_name,
                 input_tokens=inp_tokens, output_tokens=out_tokens)

    def _parse_tool_response(self, *, resp, tool_name: str, output_schema: type[T]) -> T:
        """Extract the tool_use block from the response and instantiate output_schema.

        Raises RuntimeError if the model did not return a tool_use block.
        """
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                return output_schema(**block.input)
        raise RuntimeError(
            f"Anthropic returned no tool_use block for {tool_name!r}. "
            f"stop_reason={resp.stop_reason}; content={resp.content!r}"
        )
```

Add `T` to the public re-exports in `app/inferencing/_base.py` so the import above works. Edit `app/inferencing/_base.py`: ensure `T = TypeVar("T", bound=BaseModel)` is module-level (it already is per Task 2).

- [ ] **3.4 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py -q && make test
```

Expected: all green.

- [ ] **3.5 Commit.**

```bash
git add app/inferencing/anthropic.py tests/unit/test_framework_primitives.py
git commit -m "$(cat <<'EOF'
feat(inferencing): add AnthropicProvider implementation

Mirrors app/services/llm_provider.py's AnthropicProvider, conforming to
the new Provider Protocol. Old file remains in place; this is added
alongside so subsequent sub-plans can switch call sites incrementally.
EOF
)"
```

---

## Task 4 — `Tuning` base + `PipelineTuning` in `app/pipelines/tuning.py`

**Files:**
- Create: `app/pipelines/tuning.py`
- Test: `tests/unit/test_framework_primitives.py` (extend)

- [ ] **4.1 Write the failing test.**

Append to `tests/unit/test_framework_primitives.py`:

```python
def test_pipeline_tuning_loads_defaults() -> None:
    """`PipelineTuning()` instantiates with documented defaults."""
    from app.pipelines.tuning import PipelineTuning, Tuning

    pt = PipelineTuning()
    assert pt.extract_confidence_gate == 0.85
    assert pt.coverage_floor == 0.80
    assert pt.dropout_floor == 0.50
    # subclass relationship lets agent tuning classes inherit later
    assert issubclass(PipelineTuning, Tuning)
```

- [ ] **4.2 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py::test_pipeline_tuning_loads_defaults -q
```

Expected: `ModuleNotFoundError: No module named 'app.pipelines.tuning'`.

- [ ] **4.3 Write minimal implementation.**

Create `app/pipelines/tuning.py`:

```python
"""Tuning base class plus pipeline-level cross-agent knobs."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Tuning(BaseSettings):
    """Base class for every tuning block — per-agent and pipeline-level."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class PipelineTuning(Tuning):
    """Cross-agent thresholds shared by every component of the extract pipeline."""

    extract_confidence_gate: float = 0.85
    coverage_floor: float = 0.80
    dropout_floor: float = 0.50
```

- [ ] **4.4 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py -q && make test
```

Expected: green.

- [ ] **4.5 Commit.**

```bash
git add app/pipelines/tuning.py tests/unit/test_framework_primitives.py
git commit -m "$(cat <<'EOF'
feat(pipelines): add Tuning base + PipelineTuning defaults

Pydantic-settings base for every per-agent and pipeline-level tuning
block. PipelineTuning carries the three cross-agent thresholds
(0.85 / 0.80 / 0.50) as documented defaults.
EOF
)"
```

---

## Task 5 — New `@tool` decorator + registry in `app/tools/`

The new registry mirrors `app/repositories/workbook_tools/_registry.py` (telemetry-instrumented; raises on duplicate; `get()` raises KeyError). The new module is `app/tools/_registry.py` with the registry instance and `app/tools/_decorator.py` re-exporting `tool` for the spec-mandated split.

**Files:**
- Create: `app/tools/_registry.py`
- Create: `app/tools/_decorator.py`
- Test: `tests/unit/test_framework_primitives.py` (extend)

- [ ] **5.1 Write the failing test.**

Append to `tests/unit/test_framework_primitives.py`:

```python
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
```

- [ ] **5.2 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py::test_tool_decorator_registers_callable -q
```

Expected: `ModuleNotFoundError: No module named 'app.tools._registry'`.

- [ ] **5.3 Write minimal implementation.**

Create `app/tools/_registry.py`:

```python
"""Tool registry — name to callable map for `@tool`-decorated helpers."""
from __future__ import annotations

import functools
import time
from collections.abc import Callable

from app.core.logs import get_logger
from app.core.telemetry import tool_calls_total, tool_duration_seconds, tool_errors_total


_log = get_logger("app.tools")


class ToolRegistry:
    """Name to callable map. The module-level `TOOL_REGISTRY` is the single instance."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}

    def register(self, name: str) -> Callable:
        """Return a decorator that wraps `fn` with OTel instrumentation and stores it under `name`."""
        def decorator(fn: Callable) -> Callable:
            if name in self._tools:
                raise ValueError(f"tool {name!r} already registered")

            @functools.wraps(fn)
            def _counted(*args, **kwargs):
                tool_calls_total.add(1, {"tool_name": name})
                t0 = time.monotonic()
                _log.debug("tool_call_start", tool_name=name)
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    _log.warning("tool_call_failed", tool_name=name, error=str(exc))
                    tool_errors_total.add(1, {"tool_name": name})
                    raise
                finally:
                    tool_duration_seconds.record(
                        time.monotonic() - t0, {"tool_name": name}
                    )

            self._tools[name] = _counted
            return fn
        return decorator

    def get(self, name: str) -> Callable:
        """Return the instrumented callable for `name`, raising KeyError if absent."""
        if name not in self._tools:
            raise KeyError(f"tool {name!r} not registered")
        return self._tools[name]

    def names(self) -> list[str]:
        """Return all registered tool names in sorted order."""
        return sorted(self._tools.keys())


TOOL_REGISTRY = ToolRegistry()
```

Create `app/tools/_decorator.py`:

```python
"""`@tool` decorator — registers a function in the global TOOL_REGISTRY."""
from __future__ import annotations

from collections.abc import Callable

from app.tools._registry import TOOL_REGISTRY


def tool(name: str | None = None) -> Callable:
    """Register the decorated function in `TOOL_REGISTRY` under `name` (defaults to its `__name__`)."""
    def decorator(fn: Callable) -> Callable:
        registered_name = name or fn.__name__
        return TOOL_REGISTRY.register(registered_name)(fn)
    return decorator
```

- [ ] **5.4 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py -q && make test
```

Expected: green.

- [ ] **5.5 Commit.**

```bash
git add app/tools/_registry.py app/tools/_decorator.py tests/unit/test_framework_primitives.py
git commit -m "$(cat <<'EOF'
feat(tools): add @tool decorator + TOOL_REGISTRY

New registry mirrors workbook_tools/_registry.py with OTel instrumentation,
duplicate-registration guard, and a `get()` lookup. `@tool('name')` is the
sole entry point; the old registry remains for the existing tools until
sub-plan 5 migrates them.
EOF
)"
```

---

## Task 6 — `Component` base in `app/components/_base.py`

The Component base is a thin wrapper around Haystack's `@component`. Subclasses still apply the decorator and declare `@component.output_types(...)`. The base is mostly a marker class so the pipeline factory in sub-plan 5 can type-check arguments, and it carries a structlog logger and one default lifecycle hook (`on_error`) for symmetry with Agent.

**Files:**
- Create: `app/components/_base.py`
- Test: `tests/unit/test_framework_primitives.py` (extend)

- [ ] **6.1 Write the failing test.**

Append to `tests/unit/test_framework_primitives.py`:

```python
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
```

- [ ] **6.2 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py::test_component_base_runs_under_haystack -q
```

Expected: `ModuleNotFoundError: No module named 'app.components._base'`.

- [ ] **6.3 Write minimal implementation.**

Create `app/components/_base.py`:

```python
"""Component base — marker class wrapping Haystack `@component`-decorated units."""
from __future__ import annotations

from app.core.logs import get_logger


class Component:
    """Base class for every pipeline component (deterministic or LLM-backed).

    Subclasses are expected to apply Haystack's `@component` decorator at the
    class level and declare `@component.output_types(...)` on their `run`
    method. The base contributes a per-instance structlog logger and serves
    as a type marker for the `make_pipeline` factory.
    """

    def __init__(self) -> None:
        self.log = get_logger(self.__class__.__module__)
```

- [ ] **6.4 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py -q && make test
```

Expected: green.

- [ ] **6.5 Commit.**

```bash
git add app/components/_base.py tests/unit/test_framework_primitives.py
git commit -m "$(cat <<'EOF'
feat(components): add Component base class

Thin marker wrapping Haystack `@component`-decorated units. Subclasses
still apply `@component` and `@component.output_types`; the base
contributes a per-instance logger and a type anchor for the upcoming
make_pipeline() factory.
EOF
)"
```

---

## Task 7 — `Agent[InputsT, OutputT]` generic base in `app/agents/_base.py`

The new `Agent` is the closed system from spec §5 — but the lifecycle hooks (`validate_input`, `validate_output`, `before_run`, `after_run`, `on_retry`) default to no-ops. Real semantic-gate behaviour ships in sub-plan 3. The retry-on-schema-validation-error semantics are copied verbatim from today's `AgentRunner._invoke_llm` + `_build_retry_prompt` so this base is a drop-in replacement once subclasses migrate.

**Files:**
- Create: `app/agents/_base.py`
- Test: `tests/unit/test_framework_primitives.py` (extend)

- [ ] **7.1 Write the failing test.**

Append to `tests/unit/test_framework_primitives.py`:

```python
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
```

- [ ] **7.2 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py::test_agent_base_runs_and_lifecycle_hooks_are_noops -q
```

Expected: `ModuleNotFoundError: No module named 'app.agents._base'`.

- [ ] **7.3 Write minimal implementation.**

Create `app/agents/_base.py`:

```python
"""Agent generic base — single LLM call with schema-retry and lifecycle-hook slots.

The lifecycle hooks (`before_run`, `validate_input`, `validate_output`,
`after_run`, `on_retry`) default to no-ops. Sub-plan 3 fills them in. This
file preserves today's `AgentRunner` retry-on-schema-failure semantics so
migrating subclasses do not change behaviour.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.logs import get_logger
from app.core.telemetry import agent_calls_total, agent_duration_seconds, agent_retry_count
from app.core.tracing import get_tracer
from app.inferencing._base import Provider
from app.pipelines.tuning import Tuning


InputsT = TypeVar("InputsT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)

log = get_logger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    """Immutable policy controlling how many extra retries are allowed on schema-validation failure."""

    max_retries: int = 1


@dataclass
class AgentRunFailure:
    """Returned (not raised) when all retry attempts are exhausted without a valid schema response."""

    agent_name: str
    attempt_count: int
    final_error: str
    raw_outputs: list[str] = field(default_factory=list)


class Agent(Generic[InputsT, OutputT]):
    """Closed-system base for one narrow LLM mapping job per subclass.

    Subclasses set the four class attributes (`name`, `prompt`, `output_schema`,
    `tuning`) and implement `build_input(ctx, inputs) -> str`. The lifecycle
    hooks are slots: override in subclasses to add per-agent gate behaviour;
    the defaults below are no-ops, preserving today's AgentRunner semantics.
    """

    name: str = ""
    prompt: str = ""
    output_schema: type[BaseModel]
    tuning: Tuning
    retry: RetryPolicy = RetryPolicy()
    tool_name: str | None = None

    def build_input(self, ctx: object, inputs: InputsT) -> str:
        """Return the user-prompt text for this run. Subclasses must override."""
        raise NotImplementedError

    def validate_input(self, user_text: str) -> bool:
        """Return True if `user_text` is acceptable. Default: always True (no-op slot)."""
        return True

    def validate_output(self, output: OutputT, ctx: object) -> bool:
        """Return True if `output` is semantically acceptable. Default: True (no-op slot)."""
        return True

    def before_run(self, ctx: object, inputs: InputsT) -> None:
        """Hook fired once before the first attempt. Default: no-op slot."""
        return None

    def after_run(self, result: OutputT | AgentRunFailure, attempts: int) -> None:
        """Hook fired once after the final attempt. Default: no-op slot."""
        return None

    def on_retry(self, reason: str, attempt: int) -> None:
        """Hook fired before each retry attempt with the reason for retry. Default: no-op slot."""
        return None

    def run(
        self,
        ctx: object,
        inputs: InputsT,
        provider: Provider,
    ) -> OutputT | AgentRunFailure:
        """Execute the agent and return the validated output or an `AgentRunFailure`."""
        self.before_run(ctx, inputs)
        user = self.build_input(ctx, inputs)
        self.validate_input(user)  # default no-op; subclasses may override

        result = self._run_with_retries(user)
        attempts = result[1]
        self.after_run(result[0], attempts)
        return result[0]

    def _run_with_retries(self, user: str) -> tuple[OutputT | AgentRunFailure, int]:
        """Drive the retry loop and return `(result, attempts)`."""
        tool_name = self.tool_name or f"emit_{self.name}"
        attempt = 0
        last_error = ""
        run_t0 = time.monotonic()
        log.info("agent_run_start", agent=self.name)

        with get_tracer(__name__).start_as_current_span(f"agent.{self.name}") as span:
            span.set_attribute("agent.name", self.name)
            while attempt <= self.retry.max_retries:
                attempt += 1
                try:
                    parsed = self._invoke_provider(tool_name, user)
                    self._record_success(attempt, span)
                    return parsed, attempt
                except ValidationError as exc:
                    last_error = str(exc)
                    agent_retry_count.add(1, {"agent": self.name, "reason": "schema_validation"})
                    log.warning("agent_run_schema_validation_failed",
                                agent=self.name, attempt=attempt, error=last_error)
                    if attempt > self.retry.max_retries:
                        break
                    user = _build_retry_prompt(user, last_error)
                    self.on_retry("schema_validation", attempt)
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    log.error("agent_run_unexpected_error", agent=self.name, error=last_error)
                    if attempt > self.retry.max_retries:
                        break

            failure = self._record_failure(run_t0, attempt, last_error, span)
            return failure, attempt

    def _invoke_provider(self, tool_name: str, user: str) -> OutputT:
        """Call the LLM provider and return a parsed model. Raises on schema or SDK errors."""
        t0 = time.monotonic()
        out = self._provider.complete_with_schema(
            system=self.prompt,
            user=user,
            output_schema=self.output_schema,
            tool_name=tool_name,
            agent_name=self.name,
        )
        agent_duration_seconds.record(
            time.monotonic() - t0, {"agent": self.name, "status": "success"},
        )
        agent_calls_total.add(1, {"agent": self.name, "status": "success"})
        return out  # type: ignore[return-value]

    def _record_success(self, attempt: int, span: object) -> None:
        """Log + tag span on success."""
        log.info("agent_run_success", agent=self.name, attempt=attempt)
        span.set_attribute("agent.status", "success")

    def _record_failure(
        self, run_t0: float, attempt: int, last_error: str, span: object,
    ) -> AgentRunFailure:
        """Emit failure telemetry and return an AgentRunFailure for the caller."""
        agent_duration_seconds.record(
            time.monotonic() - run_t0, {"agent": self.name, "status": "failure"},
        )
        agent_calls_total.add(1, {"agent": self.name, "status": "failure"})
        span.set_attribute("agent.status", "failure")
        span.set_attribute("agent.error", str(last_error)[:200])
        return AgentRunFailure(
            agent_name=self.name,
            attempt_count=attempt,
            final_error=last_error,
        )

    # The `run` entry point above passes the provider through a transient
    # attribute so `_invoke_provider` can stay parameter-light. Set just
    # before each call; cleared on exit is unnecessary because each `run`
    # overwrites it.
    _provider: Provider

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)


def _build_retry_prompt(user: str, validation_error: str) -> str:
    """Append the previous attempt's validation error to the user prompt for the next retry."""
    return (
        user
        + "\n\n# Previous attempt failed validation:\n"
        + validation_error
        + "\n\nPlease emit a result that matches the schema exactly."
    )
```

After writing the body above, edit `Agent.run` so the provider lands on the instance before `_run_with_retries` reads it. Replace the body of `Agent.run` (and keep the existing `before_run` / `validate_input` calls) with:

```python
    def run(
        self,
        ctx: object,
        inputs: InputsT,
        provider: Provider,
    ) -> OutputT | AgentRunFailure:
        """Execute the agent and return the validated output or an `AgentRunFailure`."""
        self._provider = provider
        self.before_run(ctx, inputs)
        user = self.build_input(ctx, inputs)
        self.validate_input(user)

        result, attempts = self._run_with_retries(user)
        self.after_run(result, attempts)
        return result
```

- [ ] **7.4 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py -q && make test
```

Expected: all green.

- [ ] **7.5 Commit.**

```bash
git add app/agents/_base.py tests/unit/test_framework_primitives.py
git commit -m "$(cat <<'EOF'
feat(agents): add Agent[InputsT, OutputT] generic base

Closed-system base for one narrow LLM mapping job per subclass.
Retry-on-schema-validation semantics are copied from the current
AgentRunner; lifecycle hooks (validate_input/validate_output/before_run/
after_run/on_retry) are no-op slots that sub-plan 3 fills in.
EOF
)"
```

---

## Task 8 — `make_pipeline()` helper in `app/pipelines/_base.py`

The helper is intentionally thin: full wiring lands in sub-plan 5. This file just exposes a factory that returns a Haystack `Pipeline` after adding the supplied components.

**Files:**
- Create: `app/pipelines/_base.py`
- Test: `tests/unit/test_framework_primitives.py` (extend)

- [ ] **8.1 Write the failing test.**

Append to `tests/unit/test_framework_primitives.py`:

```python
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
```

- [ ] **8.2 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py::test_make_pipeline_returns_haystack_pipeline_with_components -q
```

Expected: `ModuleNotFoundError: No module named 'app.pipelines._base'`.

- [ ] **8.3 Write minimal implementation.**

Create `app/pipelines/_base.py`:

```python
"""Pipeline factory helper — composes Haystack `Pipeline` from named Components."""
from __future__ import annotations

from haystack import Pipeline

from app.components._base import Component


def make_pipeline(*components: tuple[str, Component]) -> Pipeline:
    """Return a Haystack Pipeline with each `(name, component)` pair added.

    Edge wiring (`pipeline.connect`) is intentionally left to the caller and
    will be populated by sub-plan 5's `make_extract_pipeline()`.
    """
    pipeline = Pipeline()
    for name, comp in components:
        pipeline.add_component(name, comp)
    return pipeline
```

- [ ] **8.4 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py -q && make test
```

Expected: green.

- [ ] **8.5 Commit.**

```bash
git add app/pipelines/_base.py tests/unit/test_framework_primitives.py
git commit -m "$(cat <<'EOF'
feat(pipelines): add make_pipeline factory helper

Thin Haystack Pipeline factory: takes (name, component) pairs and adds
each. Edge wiring lands in sub-plan 5 with make_extract_pipeline().
EOF
)"
```

---

## Task 9 — Shared prompt fragment in `app/prompts/_shared.py`

The new module holds the text of `app/prompts/_shared.md` as a single string constant. `app/prompts/__init__.py` is **not** touched in this sub-plan — the existing prompt-loader still uses `_shared.md`; sub-plan 4 retires the file when it migrates the four prompts.

**Files:**
- Create: `app/prompts/_shared.py`
- Test: `tests/unit/test_framework_primitives.py` (extend)

- [ ] **9.1 Write the failing test.**

Append to `tests/unit/test_framework_primitives.py`:

```python
def test_shared_prompt_is_importable_string() -> None:
    """`SHARED` exposes the shared prompt header as a non-empty string."""
    from app.prompts._shared import SHARED

    assert isinstance(SHARED, str)
    assert "Glossary" in SHARED
    assert "TNA" in SHARED
    assert "PLI" in SHARED
```

- [ ] **9.2 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py::test_shared_prompt_is_importable_string -q
```

Expected: `ModuleNotFoundError: No module named 'app.prompts._shared'` (the `.py` form does not exist yet — the existing `.md` file is not a Python module).

- [ ] **9.3 Write minimal implementation.**

Create `app/prompts/_shared.py` with the entire current content of `app/prompts/_shared.md` pasted into a single `SHARED` constant:

```python
"""Shared prompt header — glossary + faithful-extraction + output-discipline."""
from __future__ import annotations

SHARED: str = """# Glossary

- **TNA** — Time and Action: production schedule with planned dates + qty per stage.
- **PLI** — Production Line Item: one row in a TNA (unique style + color + fabric).
- **IO Number** — Internal Order number. One TNA can have multiple PLI rows.
- **Stage** — Production milestone (e.g. Cutting, Sewing, Inspection) with a planned date.

# Faithful extraction principles

- TNA is source of truth. Do not split cells across multiple fields.
- If a cell holds combined "code + name", route to the *_code variant.
- "Original Order Received", "Factory Confirmed", "Etd Ex factory as per P.O" are
  lifecycle / PO fields — NOT stages.
- Quantity columns (Cut Qty, Sewing Qty, Color Qty, Shipped Qty) are NOT stages.
- A stage is a phase of manufacturing where physical work happens, not just any
  cell that holds a date.

# Output discipline

- Match canonical fields by HEADER TEXT, not column position.
- Treat a stray date or integer in a header cell as a MISSING header — don't
  use it as a field anchor.
- For single-column code+name content, always use *_code.
"""
```

- [ ] **9.4 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py -q && make test
```

Expected: green.

- [ ] **9.5 Commit.**

```bash
git add app/prompts/_shared.py tests/unit/test_framework_primitives.py
git commit -m "$(cat <<'EOF'
feat(prompts): add SHARED prompt constant module

Mirrors app/prompts/_shared.md into a Python module-level string so
sub-plan 4 can import it from app.prompts._shared without going through
the prompt_loader file-reading path. The .md file is left in place
until sub-plan 4 retires the loader.
EOF
)"
```

---

## Task 10 — `app/artifacts/__init__.py` re-exports from `app.models.artifacts`

Re-exports are explicit (not `import *`), so the public surface is auditable.

**Files:**
- Modify: `app/artifacts/__init__.py`
- Test: `tests/unit/test_framework_primitives.py` (extend)

- [ ] **10.1 Write the failing test.**

Append to `tests/unit/test_framework_primitives.py`:

```python
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
```

- [ ] **10.2 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py::test_artifacts_package_reexports_models -q
```

Expected: `AssertionError: app.artifacts missing 'SheetPlan'` (or similar).

- [ ] **10.3 Write minimal implementation.**

Replace the body of `app/artifacts/__init__.py` (currently a one-line docstring) with explicit re-exports:

```python
"""Artifact primitives — re-exports of pipeline-shared Pydantic models.

This package is a bridge during the architecture redesign: imports
from `app.artifacts` keep working as the underlying types are
eventually split out of `app.models.artifacts` in sub-plan 5.
"""
from __future__ import annotations

from app.models.artifacts import (
    CanonicalNameMap,
    HeaderLabel,
    KVAnchor,
    LayoutHints,
    PlanVerdict,
    PliBlock,
    RowSpec,
    SheetPlan,
    SheetSignals,
    StageBandSpec,
    StageColumn,
    ValidationFinding,
    ValidationFindings,
)


__all__ = [
    "CanonicalNameMap",
    "HeaderLabel",
    "KVAnchor",
    "LayoutHints",
    "PlanVerdict",
    "PliBlock",
    "RowSpec",
    "SheetPlan",
    "SheetSignals",
    "StageBandSpec",
    "StageColumn",
    "ValidationFinding",
    "ValidationFindings",
]
```

If any of those class names is not present in `app/models/artifacts.py` (verify by `grep -n '^class ' app/models/artifacts.py`), drop the missing name from both the import block and `__all__`, and remove the matching entry from the test's `expected` tuple. Do not invent re-exports.

- [ ] **10.4 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py -q && make test
```

Expected: green.

- [ ] **10.5 Commit.**

```bash
git add app/artifacts/__init__.py tests/unit/test_framework_primitives.py
git commit -m "$(cat <<'EOF'
feat(artifacts): re-export artifact models from app.artifacts

Bridge package — `from app.artifacts import SheetPlan` works alongside
`from app.models.artifacts import SheetPlan` so sub-plan 5 can switch
call sites incrementally without a flag day.
EOF
)"
```

---

## Task 11 — End-to-end composition test

A single integration test proves the new primitives fit together: an `Agent` subclass, a `Component` wrapping it, a `Pipeline` built via `make_pipeline`, and a `@tool`-decorated helper called from the agent's `build_input`. No live LLM — uses a fake provider.

**Files:**
- Modify: `tests/unit/test_framework_primitives.py` (append)

- [ ] **11.1 Write the failing test.**

Append to `tests/unit/test_framework_primitives.py`:

```python
def test_end_to_end_composition_smoke() -> None:
    """Agent + Component + Pipeline + @tool compose without runtime errors."""
    from haystack import component as hs_component
    from pydantic import BaseModel

    from app.agents._base import Agent
    from app.components._base import Component
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

    class _FakeProvider:
        model = "fake"

        def complete_with_schema(self, *, system, user, output_schema, tool_name, agent_name):
            return output_schema(v=int(user.strip()))

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

        def __init__(self, provider: object) -> None:
            super().__init__()
            self._agent = _SmokeAgent()
            self._provider = provider

        @hs_component.output_types(out=_Out)
        def run(self, x: int) -> dict:
            return {"out": self._agent.run(ctx=None, inputs=_Inputs(x=x), provider=self._provider)}

    pipeline = make_pipeline(("smoke", _SmokeComponent(_FakeProvider())))
    assert "smoke" in pipeline.graph.nodes
    result = pipeline.run({"smoke": {"x": 7}})
    assert result["smoke"]["out"].v == 14
```

- [ ] **11.2 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py::test_end_to_end_composition_smoke -q
```

Expected: pass on the first try if all earlier tasks landed cleanly. If it fails, the failure pinpoints which primitive is misaligned — fix that primitive (not this test).

- [ ] **11.3 Write minimal implementation.**

No new implementation is required: this task exists to lock the contract between primitives. If 11.2 fails, revisit the affected earlier task; do not work around it here.

- [ ] **11.4 Run pytest.**

```bash
pytest tests/unit/test_framework_primitives.py -q && make test
```

Expected: full suite green.

- [ ] **11.5 Commit.**

```bash
git add tests/unit/test_framework_primitives.py
git commit -m "$(cat <<'EOF'
test(framework): end-to-end composition smoke test

Asserts an Agent + Component + Pipeline + @tool combination wires up
and runs without error using a FakeLLM-style provider. Locks the
inter-primitive contract before sub-plan 2 builds on it.
EOF
)"
```

---

## Exit criteria for this sub-plan

- [ ] `make test` green (252 pre-existing + 8+ new framework tests).
- [ ] `app/services/`, `app/repositories/workbook_tools/`, `app/prompts/workflow/` untouched.
- [ ] FastAPI route `/extract` still serves an extraction (manual `make up` + curl, optional smoke).
- [ ] New imports compose: `Agent`, `Component`, `Provider`, `make_pipeline`, `tool`, `TOOL_REGISTRY`, `PipelineTuning`, `Tuning`, `AnthropicProvider`, `SHARED`, plus every artifact class re-export.
- [ ] No reference to plan-task names ("Task 7", "Sub-plan 1") appears in any committed source file or docstring.

When all boxes above are checked, this sub-plan is done. Sub-plan 2 (train-of-thought capture) begins by extending `app/inferencing/anthropic.py` and `app/agents/_base.py` in place.
