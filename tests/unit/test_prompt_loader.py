"""Tests for app/core/prompt_loader."""
from app.core.prompt_loader import load_prompt


def test_load_prompt_resolves_shared_fragment(tmp_path):
    shared = tmp_path / "_shared.md"
    shared.write_text("[shared content]", encoding="utf-8")
    agent = tmp_path / "myagent.md"
    agent.write_text("[agent body]\n\n{{SHARED}}\n", encoding="utf-8")

    text = load_prompt(agent, shared_fragment=shared)
    assert "[agent body]" in text
    assert "[shared content]" in text
    assert "{{SHARED}}" not in text


def test_load_prompt_without_shared(tmp_path):
    p = tmp_path / "only.md"
    p.write_text("hello", encoding="utf-8")
    assert load_prompt(p) == "hello"
