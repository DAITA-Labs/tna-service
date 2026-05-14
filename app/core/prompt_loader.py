"""Prompt loader — read .md prompt files, optionally splice a shared fragment.

Workflow prompts contain a `{{SHARED}}` placeholder; the loader replaces it
with the contents of `app/prompts/_shared.md` so the glossary + principles
block lives in one place and every agent shares it.
"""
from __future__ import annotations
from pathlib import Path


def load_prompt(path: Path | str, shared_fragment: Path | str | None = None) -> str:
    """Read `path` as utf-8 and return its text, splicing in `shared_fragment` if given.

    If `shared_fragment` is provided, replaces every `{{SHARED}}` placeholder in
    the prompt text with the fragment's contents.
    """
    text = Path(path).read_text(encoding="utf-8")
    if shared_fragment is not None:
        shared = Path(shared_fragment).read_text(encoding="utf-8")
        text = text.replace("{{SHARED}}", shared)
    return text
