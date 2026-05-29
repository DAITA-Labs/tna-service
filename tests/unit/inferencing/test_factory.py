"""Provider factory — dispatch coverage + registration mechanism."""
from __future__ import annotations

import pytest

from app.inferencing import factory as factory_module
from app.inferencing._base import BaseProvider
from app.inferencing.factory import (
    UnknownProviderError,
    build_provider,
    register_provider,
    registered_providers,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


class _FakeProvider(BaseProvider):
    """Bare-minimum BaseProvider used for factory dispatch tests."""

    model = "fake-model-v1"

    def _call_provider(self, *, system, user, output_schema, tool_name):  # type: ignore[override]
        raise NotImplementedError

    def _record_usage(self, *, raw, tin, tout, agent_name):  # type: ignore[override]
        return None

    def _parse_response(self, *, raw, tool_name, output_schema):  # type: ignore[override]
        raise NotImplementedError

    def _extract_tokens(self, raw):  # type: ignore[override]
        return (0, 0)

    def _extract_raw_text(self, raw):  # type: ignore[override]
        return ""


@pytest.fixture
def isolated_registry(monkeypatch):
    """Swap the module registry for an isolated copy so tests don't pollute it."""
    monkeypatch.setattr(factory_module, "_PROVIDER_LOADERS", {})
    yield


# ── Tests ───────────────────────────────────────────────────────────────────


def test_register_provider_makes_it_dispatchable(isolated_registry) -> None:
    register_provider("fake", lambda: _FakeProvider())
    assert "fake" in registered_providers()


def test_build_provider_returns_registered_instance(isolated_registry) -> None:
    register_provider("fake", lambda: _FakeProvider())
    p = build_provider("fake")
    assert isinstance(p, _FakeProvider)
    assert p.model == "fake-model-v1"


def test_build_provider_is_case_insensitive(isolated_registry) -> None:
    register_provider("fake", lambda: _FakeProvider())
    assert isinstance(build_provider("FAKE"), _FakeProvider)
    assert isinstance(build_provider("Fake"), _FakeProvider)


def test_register_provider_lowercases_name(isolated_registry) -> None:
    register_provider("MyCloud", lambda: _FakeProvider())
    assert "mycloud" in registered_providers()
    assert "MyCloud" not in registered_providers()


def test_unknown_provider_raises_with_helpful_message(isolated_registry) -> None:
    register_provider("only_thing", lambda: _FakeProvider())
    with pytest.raises(UnknownProviderError) as exc_info:
        build_provider("missing_one")
    msg = str(exc_info.value)
    assert "missing_one" in msg
    assert "only_thing" in msg
    assert "register_provider" in msg


def test_build_provider_default_uses_settings(isolated_registry, monkeypatch) -> None:
    """When name is None, the factory reads Settings.llm_provider."""
    register_provider("fake", lambda: _FakeProvider())

    from app.config import settings as settings_module
    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "fake")

    p = build_provider()
    assert isinstance(p, _FakeProvider)

    settings_module.get_settings.cache_clear()
