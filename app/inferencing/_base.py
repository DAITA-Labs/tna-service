"""LLM provider base — template method + abstract primitives for inferencing backends.

`BaseProvider` owns the orchestration of every LLM call: OTel span, latency
metric, success counter, structured logging, and the request/response span
events that carry the train-of-thought capture contract. Concrete subclasses
implement five provider-specific primitives — `_call_provider`,
`_record_usage`, `_parse_response`, `_extract_tokens`, `_extract_raw_text`.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

from app.core.logs import get_logger
from app.core.telemetry import llm_calls_total, llm_inference_duration_seconds
from app.core.tracing import get_tracer
from app.inferencing.capture import record_request_event, record_response_event


T = TypeVar("T", bound=BaseModel)

log = get_logger(__name__)


class BaseProvider(ABC):
    """Template-method base for an LLM provider returning schema-validated output.

    Subclasses set the `model` attribute and implement five primitives:
    `_call_provider`, `_extract_tokens`, `_extract_raw_text`, `_record_usage`,
    `_parse_response`. The template method `complete_with_schema` owns the
    OTel span, latency metric, success counter, structured logging, and the
    train-of-thought capture events.
    """

    model: str
    max_tokens: int = 4096
    temperature: float = 0.0

    def complete_with_schema(
        self,
        *,
        system: str,
        user: str,
        output_schema: type[T],
        tool_name: str,
        agent_name: str = "unknown",
        attempt: int = 1,
    ) -> tuple[T, str, int, int]:
        """Call the LLM and return `(parsed, raw_text, tokens_in, tokens_out)`."""
        log.debug("llm_call_start", model=self.model, tool=tool_name,
                  system_chars=len(system), user_chars=len(user))
        t0 = time.monotonic()
        with get_tracer(__name__).start_as_current_span("llm.complete") as span:
            span.set_attribute("llm.model", self.model)
            span.set_attribute("llm.agent", agent_name)
            record_request_event(
                span, model=self.model, max_tokens=self.max_tokens,
                temperature=self.temperature, attempt=attempt,
            )
            raw = self._call_provider(
                system=system, user=user,
                output_schema=output_schema, tool_name=tool_name,
            )
            duration_ms = (time.monotonic() - t0) * 1000.0
            tokens_in, tokens_out = self._extract_tokens(raw)
            raw_text = self._extract_raw_text(raw, tool_name)
            record_response_event(
                span, raw=raw_text, tokens_out=tokens_out or 0,
                duration_ms=duration_ms, attempt=attempt,
            )
            llm_inference_duration_seconds.record(
                duration_ms / 1000.0, {"model": self.model},
            )
            llm_calls_total.add(1, {"model": self.model, "status": "success"})
            self._record_usage(span=span, raw=raw, agent_name=agent_name)
            parsed = self._parse_response(
                raw=raw, tool_name=tool_name, output_schema=output_schema,
            )
            return parsed, raw_text, tokens_in or 0, tokens_out or 0

    @abstractmethod
    def _call_provider(
        self, *, system: str, user: str,
        output_schema: type[T], tool_name: str,
    ):
        """Send the request to the provider and return the raw response object."""

    @abstractmethod
    def _extract_tokens(self, raw) -> tuple[int | None, int | None]:
        """Return `(input_tokens, output_tokens)` from the raw response, or (None, None)."""

    @abstractmethod
    def _extract_raw_text(self, raw, tool_name: str) -> str:
        """Return the raw text representation of the model's response."""

    @abstractmethod
    def _record_usage(self, *, span, raw, agent_name: str) -> None:
        """Emit token-count metrics and span attributes from `raw`'s usage block."""

    @abstractmethod
    def _parse_response(
        self, *, raw, tool_name: str, output_schema: type[T],
    ) -> T:
        """Extract the structured payload from `raw` and return an `output_schema` instance."""
