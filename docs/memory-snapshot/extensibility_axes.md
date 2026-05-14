---
name: TNA parser — four extensibility axes
description: How the architecture grows when new TNA patterns appear, without rewrites
type: project
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
The TNA parser architecture grows additively along four orthogonal axes; every new TNA format lands on one or two of these without rewriting existing components.

| Axis | What gets added |
|---|---|
| **A. New structural signal** | A flag/enum on `StructuralFingerprint` — Inspector detects it, orchestrator routes on it |
| **B. New pattern in a bridge artifact** | New literal value or field in `FieldMap` / `StageBand` / `PLIBoundaries` |
| **C. New specialist agent** | New graph node + Pydantic schema for a job no existing agent covers |
| **D. New tool** | New deterministic helper in the tool library |

**Why:** Resists "every new supplier = new branch" failure mode. Each new pattern is a small additive change, not a code-spreading rewrite.

**How to apply:** When a new TNA pattern surfaces, ask first: which axis (or pair) does this land on? Most discoveries are A + B (new signal + new schema literal/field). Reach for C (new agent) only when domain reasoning is genuinely new, not just a new pattern of an existing concept.

**Worked example (2026-05-08):** multi-band stages with tall sub-rows in the Orders Plan family used A + B — two literal additions to schemas + one signal flag. No agent rewrite, no graph rewrite. See `04-sessions/2026-05-08-multi-band-stages-extension.md` and `knowledge-base/tna-parser-multi-band-stages.md` in the project repo.

**Anti-pattern:** axis-A inflation. Only add a structural signal when it materially changes routing. If the new pattern is expressible by existing patterns (e.g. a new supplier label maps to existing semantic IO detection), no new signal is needed.
