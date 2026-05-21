"""Tests for the FakeLLM helper itself."""
import pytest
from pydantic import BaseModel
from tests.fixtures.fake_llm import FakeLLM


class _SchemaA(BaseModel):
    name: str


def test_fake_llm_returns_canned_response():
    llm = FakeLLM(canned={"_SchemaA": {"name": "hello"}})
    parsed, raw, tin, tout = llm.complete_with_schema(system="s", user="u",
                                                      output_schema=_SchemaA)
    assert isinstance(parsed, _SchemaA)
    assert parsed.name == "hello"
    assert raw == "{}"
    assert tin == 0 and tout == 0


def test_fake_llm_raises_when_schema_not_canned():
    llm = FakeLLM(canned={})
    with pytest.raises(AssertionError, match="no canned response for schema"):
        llm.complete_with_schema(system="s", user="u",
                                output_schema=_SchemaA)


def test_script_responses_returns_each_in_order() -> None:
    from pydantic import BaseModel
    from tests.fixtures.fake_llm import FakeLLM

    class _Demo(BaseModel):
        value: str

    llm = FakeLLM(canned={}).script_responses({"value": "first"}, {"value": "second"})

    a, *_ = llm.complete_with_schema(system="", user="", output_schema=_Demo, tool_name="t")
    b, *_ = llm.complete_with_schema(system="", user="", output_schema=_Demo, tool_name="t")

    assert a.value == "first"
    assert b.value == "second"


def test_script_responses_raises_when_exhausted() -> None:
    import pytest
    from pydantic import BaseModel
    from tests.fixtures.fake_llm import FakeLLM

    class _Demo(BaseModel):
        value: str

    llm = FakeLLM(canned={}).script_responses({"value": "only"})
    llm.complete_with_schema(system="", user="", output_schema=_Demo, tool_name="t")

    with pytest.raises(AssertionError, match="script exhausted"):
        llm.complete_with_schema(system="", user="", output_schema=_Demo, tool_name="t")
