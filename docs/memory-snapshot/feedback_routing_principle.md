---
name: Structural-signal routing over format-name branching
description: User's preference for how the TNA parser orchestrator decides extraction strategy
type: feedback
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
When designing TNA parser extraction logic, route on **structural signals** (e.g. `scattered_kv`, `multi_row_headers`, `vertical_merge_in_data`, `has_totals_rows`, `has_noise_sheets`) — never on format/supplier names (e.g. "DKN", "ChristianBerg"). No `if format == "DKN"` branches anywhere.

**Why:** User pushed back during the 2026-05-07 brainstorm on format-name routing because every unseen supplier becomes a new branch, the `else` becomes a hard failure, and agents become coupled to supplier identity. Signal-based routing degrades gracefully on novel files because they're new combinations of known signals (or fall through to a generic-explorer agent).

**How to apply:** When proposing extraction logic, agents, or orchestration nodes for this project:
- Name capabilities after **shape**, not supplier (`columnar_tabular_field_locator`, `scattered_kv_field_locator`, `vertical_merge_pli_resolver`, `noise_sheet_filter`)
- Routing decisions in the orchestrator are informed by an Inspector-emitted `StructuralFingerprint`
- Always include a generic-explorer ReAct fallback for files where no signal matches
- Log structural fingerprints on every run so recurring novel patterns can become future capabilities
