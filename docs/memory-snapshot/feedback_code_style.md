---
name: TNA parser — code style preferences (comments, function scope, structure)
description: User's code style preferences for the TNA parser experiment package
type: feedback
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
For the TNA parser experiment package (`F:\DAITA\ARENA\TNA\tna_parser\`), apply these preferences to all code:

1. **Use the project venv and requirements.txt.** Always `.venv\Scripts\python.exe` (Windows; do not activate). Refresh `F:\DAITA\ARENA\TNA\requirements.txt` with `pip freeze` after every dep add.
2. **Structured + proper naming conventions.** Snake_case for Python identifiers; module-level objects exported via explicit `__all__` when public; one responsibility per module.
3. **Enough comments.** Module-level docstrings stating purpose. Function docstrings with one-line summary + arg/return notes for non-obvious functions. Inline comments for non-obvious logic. **Override** Claude's default-no-comments stance — this user wants enough explanation that someone new can read and understand without re-deriving the design.
4. **Minimal function scope.** Each function does one thing. If a function fills with multiple responsibilities, split it. Pull pure helpers into a `utils.py` (or per-module utilities) rather than nesting complexity.
5. **End-to-end tests for each tool / module.** TDD: failing test first, then implementation. Tests should exercise real dataset files where appropriate, not just toy fixtures.
6. **No heavy / clever code.** Prefer readable + obvious over compact + clever.

**Why:** User stated this directly when authorizing implementation: "use .venv and requirements.txt and keep everything structured and proper naming conventions and enough comments and lets not have heavy complex code like filling up one function with a whole lot of responsibilities lets have minimal scope for functions and can have utilities as well... we shall build end to end tests for each tool or anything that we build here as well."

**How to apply:** Pass these as standing constraints to every subagent dispatched for this project. Verify code review against them after each task completes. If a generated function exceeds ~30 lines or has multiple responsibilities, push back and split.
