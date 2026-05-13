"""Tests for the FixtureCase helper itself."""
import pytest
from tests.fixtures.case import FixtureCase


def _make_case(expected: dict) -> FixtureCase:
    return FixtureCase(name="dummy", ctx=None, xlsx_path=None, _expected=expected)


def test_fixture_case_expectations_returns_tier_section():
    c = _make_case({"layer_expectations": {"flow": {"pli_mode": "row_per_pli"}}})
    assert c.expectations("flow") == {"pli_mode": "row_per_pli"}


def test_fixture_case_expectations_raises_when_tier_missing():
    c = _make_case({"layer_expectations": {"flow": {}}})
    with pytest.raises(AssertionError, match="no `layer_expectations.agent`"):
        c.expectations("agent")


def test_fixture_case_is_failure_case_detects_block():
    c1 = _make_case({"layer_expectations": {}})
    c2 = _make_case({"layer_expectations": {}, "failure_expectations": {"category": "x"}})
    assert c1.is_failure_case() is False
    assert c2.is_failure_case() is True


def test_fixture_case_description_default():
    c = _make_case({"layer_expectations": {}})
    assert c.description == ""
