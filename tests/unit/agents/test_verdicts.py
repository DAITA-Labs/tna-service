"""Unit tests for InputVerdict and OutputVerdict dataclass types."""
from app.agents._base import InputVerdict, OutputVerdict


def test_input_verdict_ok():
    v = InputVerdict.ok()
    assert v.is_ok
    assert not v.is_abort
    assert v.reason is None


def test_input_verdict_abort():
    v = InputVerdict.abort("missing required field")
    assert v.is_abort
    assert not v.is_ok
    assert v.reason == "missing required field"


def test_output_verdict_ok():
    v = OutputVerdict.ok()
    assert v.is_ok
    assert not v.is_retry
    assert not v.is_fail
    assert v.reason is None


def test_output_verdict_retry():
    v = OutputVerdict.retry("value out of range")
    assert v.is_retry
    assert not v.is_ok
    assert not v.is_fail
    assert v.reason == "value out of range"


def test_output_verdict_fail():
    v = OutputVerdict.fail("unrecoverable error")
    assert v.is_fail
    assert not v.is_ok
    assert not v.is_retry
    assert v.reason == "unrecoverable error"
