---
name: TNA AI Parser project overview
description: Where the TNA AI parser project lives and which docs to read first in a new session
type: project
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
Project lives in F:\DAITA\ARENA\TNA. Owner: Nagasai (nagasai@daitalabs.com). Goal: format-agnostic AI parser for TNA (Time and Action) Excel files producing structured PLI JSON. Currently in M0 (research / experiments) phase. M1 (parser proof of concept) target 2026-05-09. Production by 2026-05-16.

**Why:** Tight 10-day project window; the work spans an existing planned spec plus a new architectural direction (multi-agent + structural-signal routing) brainstormed on 2026-05-07.

**How to apply:** When resuming work in this directory, read these in order:
1. `F:\DAITA\ARENA\TNA\TNA AI parser\CLAUDE.md` — project agent context
2. `F:\DAITA\ARENA\TNA\TNA AI parser\TNA_AI_Parser_Project_Spec.md` — full spec
3. `F:\DAITA\ARENA\TNA\TNA AI parser\03-decisions\` — ADRs in numeric order; ADR-002 (4-step pipeline) was superseded by the 2026-05-07 multi-agent direction; check for ADR-003 if it has been written
4. The brainstorm design doc at `docs/superpowers/specs/2026-05-07-tna-multi-agent-orchestration-design.md` (when written) for the architecture decided in this brainstorm
