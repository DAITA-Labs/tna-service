"""Tests for the FakeLLM helper itself."""
import pytest
from pydantic import BaseModel
from tests.fixtures.fake_llm import FakeLLM


class _SchemaA(BaseModel):
    name: str


def test_fake_llm_returns_canned_response():
    llm = FakeLLM(canned={"_SchemaA": {"name": "hello"}})
    out = llm.complete_with_schema(system="s", user="u",
                                  output_schema=_SchemaA)
    assert isinstance(out, _SchemaA)
    assert out.name == "hello"


def test_fake_llm_raises_when_schema_not_canned():
    llm = FakeLLM(canned={})
    with pytest.raises(AssertionError, match="no canned response for schema"):
        llm.complete_with_schema(system="s", user="u",
                                output_schema=_SchemaA)
