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
