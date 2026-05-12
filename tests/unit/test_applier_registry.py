"""Tests for app/services/applier/_registry."""
from app.services.applier._registry import (
    pattern_handler, get_pattern_handler, list_patterns, PatternRegistry,
)


def test_register_and_lookup():
    reg = PatternRegistry()

    @reg.register("dummy_pattern")
    def handler(ctx, boundaries):
        return [1, 2, 3]

    assert reg.get("dummy_pattern")(None, None) == [1, 2, 3]
    assert "dummy_pattern" in reg.names()


def test_global_decorator():
    @pattern_handler("test_xyz")
    def h(ctx, boundaries):
        return []

    assert "test_xyz" in list_patterns()
