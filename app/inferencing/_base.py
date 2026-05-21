"""LLM provider base — template method + abstract primitives for inferencing backends.

`BaseProvider` owns the orchestration of every LLM call: OTel span, latency
metric, success counter, and structured logging. Concrete subclasses
implement three provider-specific primitives — `_call_provider`,
`_record_usage`, `_parse_response`. Test fakes either implement the same
three primitives or override `complete_with_schema` directly with canned
data.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

from app.core.logs import get_logger
from app.core.telemetry import llm_calls_total, llm_inference_duration_seconds
from app.core.tracing import get_tracer


T = TypeVar("T", bound=BaseModel)

log = get_logger(__name__)


class BaseProvider(ABC):
    """Template-method base for an LLM provider returning schema-validated output.

    Subclasses set the `model` attribute and implement three primitives:
    `_call_provider`, `_record_usage`, `_parse_response`. The concrete
    template method `complete_with_schema` owns the OTel span, latency
    metric, success counter, and structured logging — so every provider
    emits the same telemetry shape.
    """

    model: str

    def complete_with_schema(
        self,
        *,
        system: str,
        user: str,
        output_schema: type[T],
        tool_name: str,
        agent_name: str = "unknown",
    ) -> T:
        """Call the LLM and return a schema-validated Pydantic model."""
        log.debug("llm_call_start", model=self.model, tool=tool_name,
                  system_chars=len(system), user_chars=len(user))
        t0 = time.monotonic()
        with get_tracer(__name__).start_as_current_span("llm.complete") as span:
            span.set_attribute("llm.model", self.model)
            span.set_attribute("llm.agent", agent_name)
            raw = self._call_provider(
                system=system, user=user,
                output_schema=output_schema, tool_name=tool_name,
            )
            llm_inference_duration_seconds.record(
                time.monotonic() - t0, {"model": self.model},
            )
            llm_calls_total.add(1, {"model": self.model, "status": "success"})
            self._record_usage(span=span, raw=raw, agent_name=agent_name)
            return self._parse_response(
                raw=raw, tool_name=tool_name, output_schema=output_schema,
            )

    @abstractmethod
    def _call_provider(
        self, *, system: str, user: str,
        output_schema: type[T], tool_name: str,
    ):
        """Send the request to the provider and return the raw response object."""

    @abstractmethod
    def _record_usage(self, *, span, raw, agent_name: str) -> None:
        """Emit token-count metrics and span attributes from `raw`'s usage block."""

    @abstractmethod
    def _parse_response(
        self, *, raw, tool_name: str, output_schema: type[T],
    ) -> T:
        """Extract the structured payload from `raw` and return an `output_schema` instance."""
