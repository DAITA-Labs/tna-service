"""Unit tests for span-event recording helpers."""
from __future__ import annotations

from app.inferencing.capture import (
    hash_text,
    record_input_event,
    record_output_event,
    record_request_event,
    record_response_event,
    record_retry_event,
    record_validate_event,
)


class _FakeSpan:
    """In-memory span stand-in capturing add_event calls for assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def add_event(self, name: str, attributes: dict) -> None:
        self.events.append((name, attributes))


def test_hash_text_is_sha256_hex_64() -> None:
    h = hash_text("hello world")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_record_input_event_system_prompt() -> None:
    span = _FakeSpan()
    record_input_event(span, kind="system_prompt", text="SYS")
    name, attrs = span.events[0]
    assert name == "input.system_prompt"
    assert attrs["sha256"] == hash_text("SYS")
    assert attrs["length"] == 3


def test_record_input_event_user_built_with_tools() -> None:
    span = _FakeSpan()
    record_input_event(span, kind="user_built", text="USR",
                       tools_used=["peek_sheet", "survey"])
    name, attrs = span.events[0]
    assert name == "input.user_built"
    assert attrs["tools_used"] == ["peek_sheet", "survey"]


def test_record_request_event_carries_model_and_attempt() -> None:
    span = _FakeSpan()
    record_request_event(span, model="claude-sonnet-4-6",
                         max_tokens=1024, temperature=0.0, attempt=2)
    name, attrs = span.events[0]
    assert name == "llm.request_sent"
    assert attrs == {"model": "claude-sonnet-4-6", "max_tokens": 1024,
                     "temperature": 0.0, "attempt": 2}


def test_record_response_event_carries_duration_and_tokens() -> None:
    span = _FakeSpan()
    record_response_event(span, raw="raw", tokens_out=123, duration_ms=45.6)
    name, attrs = span.events[0]
    assert name == "llm.response_received"
    assert attrs["tokens_out"] == 123
    assert attrs["duration_ms"] == 45.6
    assert attrs["sha256"] == hash_text("raw")
    assert attrs["attempt"] == 1


def test_record_validate_event_ok_and_failed() -> None:
    span = _FakeSpan()
    record_validate_event(span, ok=True, error=None)
    record_validate_event(span, ok=False, error="missing field val")
    assert span.events[0] == ("llm.schema_validate", {"ok": True})
    assert span.events[1] == ("llm.schema_validate",
                              {"ok": False, "error": "missing field val"})


def test_record_output_event_schema_name() -> None:
    span = _FakeSpan()
    record_output_event(span, schema_name="CanonicalNameMap")
    assert span.events[0] == ("output.parsed_ok",
                              {"schema": "CanonicalNameMap"})


def test_record_retry_event_attempt_and_reason() -> None:
    span = _FakeSpan()
    record_retry_event(span, attempt=2, reason="schema_validation")
    assert span.events[0] == ("agent.retry",
                              {"attempt": 2, "reason": "schema_validation"})
