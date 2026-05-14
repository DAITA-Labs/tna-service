---
name: LLM as judge for SheetRowPlanner
description: For the SheetRowPlanner subsystem we lock in the "LLM-as-reviewer" pattern — deterministic Python produces the SheetPlan, LLM critiques it.
type: project
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
For the new SheetRowPlanner subsystem (being designed 2026-05-13), the LLM is a **reviewer/judge of the deterministic plan**, not the producer.

**Why:** LLMs are bad at row arithmetic (today's BoundaryFinder produces 3 PLIs for CHRISTIAN BERG when the truth is 7). LLMs are good at "does this look right?" Reviewing a concrete plan is much easier than building one from scratch and fits in ~3K tokens vs 15-25K today.

**How to apply:**
- New phase 3b `PlanReviewer` LLM agent fires only when Tier 1 (structural) or Tier 2 (statistical) det validators warn, plan confidence < ~0.85, or mode is the rarer `SECTION_PER_PLI` / `SHEET_IS_PLI`.
- Det wins on disagreement — LLM is advisory.
- LLM call failure is non-blocking (keep original plan, log the gap to telemetry so we know which det rule to add next).
- The same inversion can apply elsewhere: prefer LLM-as-reviewer over LLM-as-producer when the underlying task has a clear deterministic backbone.
