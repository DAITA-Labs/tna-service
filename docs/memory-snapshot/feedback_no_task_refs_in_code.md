---
name: TNA parser — no plan/task references in code comments or docstrings
description: User feedback: code should not reference plan-task names ("MA Task 17", "Task 5", "in plan 2") because they're irrelevant to readers and rot quickly
type: feedback
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
When writing or editing code in the `tna_parser` package, **never** reference plan task names, numbers, or phases in comments, docstrings, module headers, or `__all__` section markers.

**Bad examples — do NOT write these:**
- `# MA Task 14: FieldMap + FieldLocation + PLIMetadataLocation`
- `"""This file grows incrementally: MA Task 3 adds X, MA Task 12 adds Y."""`
- `"""Produced by: Inspector agent (MA Task 20)."""`
- `# Task 5 introduces list_sheets. Task 6 adds get_full_grid.`
- `"""Multi-agent framework. Populated in MA Tasks 18-23."""`

**Good replacements:**
- Group with semantic section headers: `# ----- Inspector outputs -----`, `# ----- PLI Boundary Finder outputs -----`
- Describe what the code does, what produces it, what consumes it — without task numbering
- Reference architectural concepts the reader can find in the design doc, not plan tasks

**Why:** Task numbers are session metadata. They mean nothing to someone reading the code in six months — neither human readers nor the orchestrator itself care which plan task created a symbol. The plan files in `05-plans/` already track that history; the source code should describe itself.

**How to apply:**
- When dispatching subagents for any task in this project, pass this constraint explicitly along with other standing constraints.
- When reviewing code (spec compliance or quality), flag any task-name references as a defect.
- The plan documents themselves are exempt — task names belong in plans, not in code.

**When this was set:** 2026-05-11 mid-plan. The user noticed accumulating `MA Task N` references in `agents/schemas.py`, `tools.py`, `models.py`, and a handful of test files. We purged them all and reset the convention.
