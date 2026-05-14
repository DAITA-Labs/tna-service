# TNA Service — Principles

These rules were established through live development experience and promoted from per-session auto-memory on 2026-05-14. They apply to all code, tests, prompts, and agent designs in this repo. Each rule is short; context is in the `Why` and `How to apply` lines.

---

## 1. Faithful extraction

**Rule:** Treat TNA cell content as the source of truth. Copy it verbatim. Never split, trim, reformat, or concatenate across cells.

**Why:** The M0 baseline lost ~30% field precision because the model split `style_code` at the first numeric token (`"890162 TAVIRA_2 522148"` → two fields). Rewriting the prompt to enforce faithful extraction recovered 71% → 100% field accuracy on the DKN benchmark. Downstream consumers depend on receiving the exact string the buyer entered; any normalisation in the parser destroys auditability.

**How to apply:**
- One cell → one field. If you can't find a field, emit `null` + a `Warning`. Don't fabricate or default.
- Two PLIs may legitimately share the same `io_number`. Don't dedupe by `io_number` anywhere.
- Stage canonicalization rule: `"Sewing Start"` + `"Sewing End"` are sub-fields of one `"Sewing"` stage. The "Start"/"Plan" date is `planned_date`; the rest go in `stage.metadata`.
- `PLI.metadata` holds non-canonical PLI-level fields (admin/lifecycle fields that have dates but are not production milestones).

---

## 2. Route on structural signals, never format or supplier names

**Rule:** Orchestrator routing must be driven by sheet shape signals (`scattered_kv`, `multi_row_headers`, `vertical_merge_in_data`, `has_totals_rows`, etc.), never by supplier or format names like `"DKN"` or `"ChristianBerg"`.

**Why:** Every unseen supplier becomes a new branch in a name-based router; the `else` becomes a hard failure. Signal-based routing degrades gracefully on novel files because they present new combinations of known signals (or fall through to the generic-explorer path). Established during the 2026-05-07 architecture brainstorm.

**How to apply:**
- Name capabilities after shape, not supplier (`kv_anchor_detector`, `row_classifier`, not `dkn_handler`).
- Routing in the orchestrator is informed by `SheetSignals` emitted by `SheetSurveyor`.
- Log `SheetSignals` on every run so recurring novel patterns can become future capabilities.
- Always include a fallback path for files where no signal matches — don't crash, emit a Warning.

---

## 3. Induction-then-apply

**Rule:** LLM induces an extraction plan from a small sample; deterministic Python applies it to all PLIs. LLM cost is bounded by sheet count, not row count.

**Why:** Asking an LLM to extract every PLI from a full 1000-row grid blows context and is non-deterministic. The SheetRowPlanner design separates: (a) inducing a `SheetPlan` (LLM-assisted, sample-sized input), from (b) applying that plan (100% deterministic, full sheet). This was the core insight of ADR-003 and the SheetRowPlanner design.

**How to apply:**
- `apply_plan` is 100% LLM-free by contract. If a case requires LLM reasoning at apply time, the planner was incomplete — fix the planner.
- `FieldNamer` sees header labels and column names, not full row data.
- `PlanReviewer` sees a plan summary + 3-5 sample rows, not the full sheet.

---

## 4. LLM as reviewer, not producer (for structured decisions)

**Rule:** When a task has a clear deterministic backbone, prefer LLM-as-reviewer over LLM-as-producer.

**Why:** LLMs are poor at row arithmetic (the prior `BoundaryFinder` agent returned 3 PLIs for CHRISTIAN BERG where the truth is 7). LLMs are good at "does this look right?" Reviewing a concrete plan is much easier than building one and fits in ~3K tokens vs 15–25K.

**How to apply:**
- `PlanReviewer` fires only when Tier 1/2 det validators warn, plan confidence < 0.85, or mode is a rarer `SECTION_PER_PLI` / `SHEET_IS_PLI`.
- Det wins on disagreement. LLM call failure is non-blocking (log to telemetry, keep original plan).
- Apply the same inversion elsewhere: if there's a deterministic backbone, build that first and use the LLM to review/refine.

---

## 5. Four extensibility axes

**Rule:** New TNA layouts are absorbed by one or two of four additive axes. Default to A + B before reaching for C or D.

| Axis | What gets added |
|---|---|
| A. New structural signal | A flag/enum on `SheetSignals` — `SheetSurveyor` detects it |
| B. New pattern in a bridge artifact | New literal/field in `SheetPlan`, `StageBandSpec`, `KVAnchor`, etc. |
| C. New specialist agent | New graph node + Pydantic schema for a genuinely new reasoning job |
| D. New tool | New deterministic helper in `app/repositories/workbook_tools/` |

**Why:** Resists "every new supplier = new branch" failure mode. The 2026-05-08 multi-band-stages discovery (Orders Plan family) used axes A + B — two literal additions and one signal flag. No agent or graph rewrite.

**How to apply:** When a new TNA pattern surfaces, ask which axis it lands on before writing any code. Only add a new signal (A) when it materially changes routing. Only add a new agent (C) when the domain reasoning is genuinely new.

---

## 6. Keep code lean — prompts before helpers

**Rule:** When iterating on a layout problem, the default order is: (1) sharpen the agent system prompt, (2) widen the sampling if the agent lacks evidence, (3) add Python helpers only when prompt + evidence demonstrably can't solve it.

**Why:** During multi-agent iteration on `63261-TNA.xlsx`, defensive guards and new helpers were added per layout, accumulating noise that obscured the actual logic. The user flagged this as "claudy code."

**How to apply:**
- Before introducing a new function, helper, or schema field for a layout fix, ask: can a prompt update or sample-widening solve this instead?
- When code is needed, fold it into the nearest existing function. Re-read the diff before declaring done and delete anything unused or hypothetical.
- Each function does one thing. If a function exceeds ~30 lines or has multiple responsibilities, split it.

---

## 7. No plan-task references in code

**Rule:** Code comments, docstrings, module headers, and `__all__` markers must never reference plan-task names or numbers (`"MA Task 17"`, `"SRP Task 12"`, `"in plan 2"`).

**Why:** Task numbers are session metadata. They mean nothing to a reader six months later. The plan files in `docs/superpowers/plans/` already track that history; source code should describe itself.

**How to apply:**
- Use semantic section headers: `# --- Inspector outputs ---`, not `# MA Task 12`.
- Describe what the code does, what produces it, what consumes it.
- When reviewing code, flag task-name references as a defect.
- Plan documents themselves are exempt.

---

## 8. Update documentation after implementation

**Rule:** Documentation (README, ARCHITECTURE, SPEC, design docs) is updated as the *last* step — after implementation, tests, and evals are all green. Not before, not concurrently.

**Why:** Documentation written before the implementation is speculative and drifts. Documentation written after is accurate and tight.

**How to apply:**
- Treat doc updates as the final task in any implementation plan.
- Update only what is now wrong. Keep diffs tight; don't touch sections unrelated to the change.
- For architectural changes: `ARCHITECTURE.md` + the relevant design doc.
- For behaviour changes: `README.md` (if user-facing) + relevant `docs/SPEC.md` sections.
- For new agents/tools: prompt files.

---

## 9. Work fluently — quality over dates

**Rule:** Do not plan or pace work against milestone deadlines. Architecture correctness and learning from real experiments take priority over sprint dates.

**Why:** The original M0–M3 window (2026-05-07 to 2026-05-16) was set during pre-kickoff scoping. After the architectural pivot and dataset complexity surfaced, the user explicitly de-prioritised dates in favour of getting the architecture right.

**How to apply:**
- Do not artificially compress task scope to fit a deadline.
- Welcome iterations that surface new patterns, even if they require schema or agent extensions.
- Reference the spec's milestone section only as historical context.
