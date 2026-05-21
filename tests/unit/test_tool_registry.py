"""Tests for app/tools/_registry."""
from app.tools._registry import (
    get_tool, list_tools, ToolRegistry,
)
from app.tools._decorator import tool


def test_register_and_lookup():
    reg = ToolRegistry()

    @reg.register("my_double")
    def doubler(x: int) -> int:
        return x * 2

    assert reg.get("my_double")(3) == 6
    assert "my_double" in reg.names()


def test_global_decorator_registers_in_default():
    @tool("my_triple")
    def tripler(x: int) -> int:
        return x * 3

    assert get_tool("my_triple")(4) == 12
    assert "my_triple" in list_tools()


def test_duplicate_name_raises():
    reg = ToolRegistry()
    reg.register("dup")(lambda: 1)
    try:
        reg.register("dup")(lambda: 2)
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "dup" in str(e)
