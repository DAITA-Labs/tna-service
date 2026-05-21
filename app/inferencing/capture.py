"""Span-event helpers that record the train-of-thought capture contract."""
from __future__ import annotations

import hashlib
from typing import Literal

from opentelemetry.trace import Span

InputKind = Literal["system_prompt", "user_built"]


def hash_text(s: str) -> str:
    """Return the sha256 hex digest of `s` encoded as utf-8."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def record_input_event(
    span: Span, *, kind: InputKind, text: str,
    tools_used: list[str] | None = None,
) -> None:
    """Record an input.<kind> span event with sha256 + length (+ tools_used)."""
    attrs: dict = {"sha256": hash_text(text), "length": len(text)}
    if kind == "user_built" and tools_used is not None:
        attrs["tools_used"] = list(tools_used)
    span.add_event(f"input.{kind}", attrs)


def record_request_event(
    span: Span, *, model: str, max_tokens: int,
    temperature: float, attempt: int = 1,
) -> None:
    """Record an llm.request_sent event immediately before the provider call."""
    span.add_event("llm.request_sent", {
        "model": model, "max_tokens": max_tokens,
        "temperature": temperature, "attempt": attempt,
    })


def record_response_event(
    span: Span, *, raw: str, tokens_out: int,
    duration_ms: float, attempt: int = 1,
) -> None:
    """Record an llm.response_received event with timing + token count + sha256."""
    span.add_event("llm.response_received", {
        "sha256": hash_text(raw),
        "tokens_out": tokens_out,
        "duration_ms": duration_ms,
        "attempt": attempt,
    })


def record_validate_event(
    span: Span, *, ok: bool, error: str | None,
) -> None:
    """Record an llm.schema_validate event with ok flag and optional error string."""
    attrs: dict = {"ok": ok}
    if not ok and error is not None:
        attrs["error"] = error
    span.add_event("llm.schema_validate", attrs)


def record_output_event(span: Span, *, schema_name: str) -> None:
    """Record an output.parsed_ok event tagged with the output schema name."""
    span.add_event("output.parsed_ok", {"schema": schema_name})


def record_retry_event(
    span: Span, *, attempt: int, reason: str,
) -> None:
    """Record an agent.retry event when a retry is about to happen."""
    span.add_event("agent.retry", {"attempt": attempt, "reason": reason})
