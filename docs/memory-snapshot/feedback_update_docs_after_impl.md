---
name: Update documentation after impl/test/eval
description: For any non-trivial implementation, update the docs (README, ARCHITECTURE, SPEC, design docs) once impl + tests + evals are green — not before.
type: feedback
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
After implementing a non-trivial change, when implementation + tests + evaluation are all green, update the relevant documentation (README.md, ARCHITECTURE.md, docs/SPEC.md, design docs under docs/superpowers/specs/, prompt files if behaviour changed).

**Why:** the user said so explicitly during the SheetRowPlanner brainstorm on 2026-05-13. Documentation that lives in the repo is the long-term record; the LLM-loaded auto-memory and brainstorm artifacts won't be there in six months.

**How to apply:**
- Treat doc updates as part of the implementation plan's *last* step — after tests + evals are green, not concurrently.
- Update only what is now wrong, not "everything mentioning this area." Keep diffs tight.
- For architectural changes: ARCHITECTURE.md + the design doc.
- For behaviour changes: README.md (if user-facing) + relevant SPEC sections.
- For new agents/tools: prompt files + the workflow inventory if one exists.
