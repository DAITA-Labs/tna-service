---
name: TNA parser — work fluently, no deadline pressure, experiment-first
description: User explicitly de-prioritized the M0/M1/M2/M3 deadlines in favor of experimenting and getting the architecture right
type: feedback
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
For the TNA parser project, do **not** plan or pace work against the original M0/M1/M2/M3 deadlines (2026-05-07 → 2026-05-16). User explicitly said: "please dont worry about the milestones or anything we can work fluently without worrying about the deadlines we need to experiment and workout architecture and the systems is the agenda."

**Why:** The originally tight 10-day window was set during pre-kickoff scoping. After the architectural pivot on 2026-05-07 (multi-agent + signal routing + induction-then-apply) and the dataset complexity surfaced during brainstorming (5+ layout families, multi-band stages, vertical merges, scattered KV), the user values **getting the architecture right and learning from real experiments** over hitting the original ship date.

**How to apply:**
- Do not artificially tighten task scope to "fit a sprint" or compress quality for delivery date
- Welcome iterations that surface new patterns even if they require schema/agent extensions (use the four extensibility axes — see `extensibility_axes.md`)
- Single-prompt baseline + multi-agent system are both valid experiments worth running fully — don't shortcut them
- Reference the spec's Section 4 milestones only as historical context; do not propose dates against them
- The CLAUDE.md "Deadline: 2026-05-16" line is **soft / aspirational** — flag any guidance that depends on it as needing user re-confirmation
