"""Provider factory — single entry point for constructing a BaseProvider.

Adding a new LLM provider is a three-step operation:

  1. Write a `BaseProvider` subclass (see `app/inferencing/anthropic.py`).
  2. At the bottom of that module, call `register_provider("<name>", <factory>)`
     where `<factory>` is a zero-arg callable returning a configured instance.
  3. Set `LLM_PROVIDER=<name>` in `.env` (or pass `name=...` to `build_provider`).

Call sites that need a provider call `build_provider()` instead of importing
a concrete class. The single config knob (`Settings.llm_provider`) decides
which provider is returned.
"""
from __future__ import annotations

from typing import Callable

from app.config import get_settings
from app.inferencing._base import BaseProvider


ProviderFactory = Callable[[], BaseProvider]


class UnknownProviderError(ValueError):
    """Raised when build_provider is asked for a name that no module has registered."""


_PROVIDER_LOADERS: dict[str, ProviderFactory] = {}


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Register a provider so `build_provider(name)` can dispatch to it.

    Call from the provider module after the class definition (see
    `app/inferencing/anthropic.py` for the reference pattern).
    """
    _PROVIDER_LOADERS[name.lower()] = factory


def build_provider(name: str | None = None) -> BaseProvider:
    """Construct a provider instance.

    If `name` is None, reads `Settings.llm_provider` (defaults to "anthropic").
    Raises `UnknownProviderError` when no module has registered the requested name.
    """
    # Import here to surface any provider self-registration that happens at
    # import time (anthropic.py calls `register_provider` when imported).
    import app.inferencing.anthropic  # noqa: F401

    resolved = (name or get_settings().llm_provider).lower()
    if resolved not in _PROVIDER_LOADERS:
        raise UnknownProviderError(
            f"Unknown LLM provider: {resolved!r}. "
            f"Registered: {sorted(_PROVIDER_LOADERS)}. "
            "Implement a BaseProvider subclass and call "
            "register_provider('<name>', <factory>) from its module."
        )
    return _PROVIDER_LOADERS[resolved]()


def registered_providers() -> list[str]:
    """Return the names of currently-registered providers, sorted."""
    import app.inferencing.anthropic  # noqa: F401

    return sorted(_PROVIDER_LOADERS)
