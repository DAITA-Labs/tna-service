"""Component base — plain class with `run` contract plus lifecycle slot hooks.

Subclasses inherit `Component` and apply Haystack's `@component` decorator at
the class level, declaring `@component.output_types(...)` on their `run`
method. The base contributes:

  - a per-instance structlog logger (`self.log`)
  - lifecycle slot hooks: `before_run`, `after_run`, `on_error`. Subclasses
    that want fallback behaviour, metric emission, or extra logging call
    these in their `run` body.

This mirrors the pattern in `app.inferencing._base.BaseProvider`. We use a
plain class with `raise NotImplementedError` for `run` rather than
`abc.ABC`+ `@abstractmethod` because Haystack's `@component` decorator
installs its own metaclass (`ComponentMeta`), which conflicts with
`ABCMeta`.
"""
from __future__ import annotations

from app.core.logs import get_logger


class Component:
    """Base for every pipeline component (deterministic or LLM-backed).

    Subclasses MUST implement `run` and apply Haystack's `@component`
    decorator at the class level. They MAY override the lifecycle hooks
    (`before_run` / `after_run` / `on_error`) to add fallback behaviour or
    extra telemetry — defaults are no-ops except `on_error`, which logs.
    """

    def __init__(self) -> None:
        self.log = get_logger(self.__class__.__module__)

    def run(self, **kwargs: object) -> dict:
        """Run the component on its inputs and return its output dict.

        Subclasses MUST override with a concrete signature matching the inputs
        they accept and apply `@component.output_types(...)` so Haystack can
        wire them into a Pipeline.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must override run() and apply "
            "Haystack's @component decorator."
        )

    def before_run(self, inputs: dict) -> None:
        """Hook fired before the body of `run`. Default: no-op slot."""

    def after_run(self, result: dict) -> None:
        """Hook fired after `run` returns successfully. Default: no-op slot."""

    def on_error(self, exc: Exception, inputs: dict) -> None:
        """Hook fired when `run` raises. Default: log the exception.

        Subclasses may override to emit metrics or set fallback state.
        The exception is re-raised by the caller regardless — this hook
        is for side effects, not for swallowing.
        """
        self.log.error(
            "component_error",
            error_type=type(exc).__name__,
            error=str(exc),
            inputs=sorted(inputs.keys()),
        )
