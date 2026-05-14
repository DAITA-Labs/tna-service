---
name: Keep the code lean — prompts before helpers
description: Each TNA layout fix should prefer prompt sharpening over adding Python helpers. Code is accumulating clutter; user flagged this in 2026-05-11 session.
type: feedback
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
When iterating on a new TNA layout, the default order of fixes is:
1. Sharpen the agent system_prompt (cheapest, no code change).
2. Widen the `build_user_input` sampling if the agent lacks evidence.
3. Only add Python helpers when prompt + evidence demonstrably cannot solve it.

When code IS needed, prefer folding it into the nearest existing function over adding a new helper / module / wrapper. Re-read the diff before declaring done and delete anything unused, duplicate, or only there to handle a hypothetical.

**Why:** User flagged during the 2026-05-11 multi-agent iteration on 63261-TNA.xlsx — "we are making a lot of changes and the code is becoming a lot of claudy so be careful of that". The pattern of adding defensive guards / new helpers / new modules for each layout was accumulating noise that obscured the actual logic.

**How to apply:** Any time you're about to introduce a new function, helper, or schema field as part of a layout-iteration fix, pause and ask: can this be a prompt update or a sample-widening instead? If yes, do that first. Also see the matching section "Keep the code lean" in `TNA AI parser/CLAUDE.md`.
