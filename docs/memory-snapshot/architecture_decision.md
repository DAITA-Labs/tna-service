---
name: TNA parser architecture (post-2026-05-07 brainstorm)
description: The three architectural pillars and the bridge artifacts the system uses
type: project
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
The TNA parser architecture (Proposed in ADR-003, supersedes ADR-002) rests on three commitments:

1. **Multi-agent specialists.** 8 agents — Inspector, Sheet Triager, Layout Classifier, Field Locator, Stage Locator, PLI Boundary Finder, Validator, Generic Explorer (fallback). Narrow input, narrow tools, narrow output. Independently testable.

2. **Structural-signal routing — never format names.** Orchestrator routes on shape (`scattered_kv`, `multi_row_headers`, `vertical_merge_in_data`, etc.) detected by the Inspector. Specialists are named after capabilities, not suppliers. See `feedback_routing_principle.md`.

3. **Induction-then-apply.** LLM induces an extraction rule from a small sample; Python applies it to all PLIs deterministically. Specialists emit Pydantic **bridge artifacts** — `FieldMap`, `StageBandSet` (containing one or more `StageBand`), `PLIBoundaries` — that Python's `apply_field_map` and `apply_stage_band_set` consume to produce the full PLI list. **LLM cost is bounded by sheet count and sample size, not row count.**

The architecture grows along four orthogonal axes (see `extensibility_axes.md`). The 2026-05-08 multi-band-stages discovery used axes A+B (new signal + new pattern in StageBand) — no agent or graph rewrite.

**Why:** Volume (large files blow context) + variety (open-ended supplier formats) + no-silent-failure (unknown layouts must produce partial output, not crash) all need to hold simultaneously. None of the three commitments alone is sufficient.

**How to apply:**
- Design doc: `F:\DAITA\ARENA\TNA\TNA AI parser\02-design\2026-05-07-multi-agent-orchestration-design.md`
- ADR: `F:\DAITA\ARENA\TNA\TNA AI parser\03-decisions\ADR-003-multi-agent-structural-signal-routing.md` (Proposed)
- When proposing extraction code or prompts, prefer the induction-then-apply form: specialist sees a sample, emits an artifact, Python iterates rows. Avoid prompts that ask the LLM to extract every PLI from a full grid.
- Sections 6.1–6.3 (orchestrator state machine, eval harness, repo structure) are paused for user review of agents/prompts before design.
