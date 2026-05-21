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

Now enforced by the agent lifecycle — see Principle 12.

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

---

## 10. Canonical PLI contract

**Rule:** A PLI must populate these as **top-level fields**, not `metadata`: `io_number`, `style_code`, `color_code`, `fabric_code`, `quantity`, `delivery_date`. A canonical value appearing in `metadata` instead of its canonical PLI field is a bug — even if extracted from the correct cell. Stage records likewise must populate `planned_date` at the top level; supporting per-stage details belong in `Stage.metadata`. Additional non-canonical PLI context (buyer, season, factory, PO number, lifecycle dates, etc.) belongs in `PLI.metadata`.

**Why:** Downstream consumers query canonical fields directly (e.g., `pli.io_number`). If a buyer-PO column gets canonicalised to `buyer_po_no` and lands in `metadata["buyer_po_no"]` because `buyer_po_no` is not a PLI field, the consumer doesn't see the data unless it knows to look. Worse, eval scorers compare label canonical fields to the extractor's PLI fields — when the extractor puts the value in `metadata`, every comparison fails. This pattern was identified during F3 diagnostic investigation (2026-05-20), where DKN/MOP files dropped `fabric_code`, `delivery_date`, `quantity` into `metadata` under canonical aliases (`fabric_quality`, `etd_ex_factory`, `order_quantity`) instead of the canonical PLI fields.

**How to apply:**
- Prefer mapping the most common canonical name. If a label says "Order Qty", map to `quantity` (PLI field), not to the more specific `order_quantity` (which becomes metadata).
- When extending FieldNamer's vocab, prefer adding aliases to existing PLI canonical fields over introducing new metadata-bound canonicals.
- If a new canonical truly needs its own PLI field (recurs across many files, downstream consumers need it directly), add it to the `PLI` Pydantic model — don't leave it stranded in `metadata`.
- During code review of any FieldNamer-prompt or apply_plan change: ask "does this map cells to PLI fields, or does it create new metadata buckets?"

---

## 11. LLM call budget — proportional to sheets

**Rule:** Total LLM calls per `/extract` invocation must scale with the count of relevant sheets in the workbook (`O(sheets)`), not with rows, PLIs, or fields. Per-sheet calls can be > 1 (currently SheetClassifier once + FieldNamer per sheet + occasionally LayoutHinter/PlanReviewer), but never per-row or per-PLI.

**Why:** The 2026-05-13 ADR-0003 brainstorm chose "induction-then-apply": LLM induces an extraction plan from a sample, deterministic Python applies it to all rows. This bound LLM cost to sheet count rather than corpus size — critical for 1000-row GUESS master files. If a future agent adds per-PLI or per-field calls, that contract breaks and cost grows unboundedly with the data. Equally, an agent whose prompt is bloated to "do three jobs in one call" (e.g., FieldNamer mapping field labels + stage names + sub-field labels + confidence values in one shot) degrades each job's quality more than splitting would — but only if the split keeps total calls `O(sheets)`.

**How to apply:**
- Before adding a new LLM call site, ask: "Is this O(sheets), or am I introducing per-row/per-PLI/per-field calls?" If the latter, redesign — find a way to keep the work deterministic, or batch into a single per-sheet call.
- An agent that does multiple distinct mapping jobs in one call should be evaluated for splitting *only* if its outputs are demonstrably lower-quality than separate focused calls would produce. Splitting costs more — needs to earn its keep on the quality metric.
- During code review: a new `await llm.complete(...)` inside a for-loop over PLIs or rows is a defect.
- Re-validate the budget after every architectural change: count actual LLM calls per file in `make eval` outputs; flag any drift from the `(1 SheetClassifier + N × FieldNamer + conditional LayoutHinter/PlanReviewer)` shape for a relevant-sheet count N.

Decision logs capture every LLM call; see ADR-0007 and observability.md.

---

## 12. Agent lifecycle is a closed system

**Rule:** Every LLM call goes through `Agent.run`. That method is the only place where schema validation and semantic validation happen, and it is the only place where retry-with-reason is allowed. Direct calls to a provider from anywhere except the `inferencing` layer are a defect.

**Why:** The lifecycle slots — `before_run`, `build_input`, `validate_input`, `validate_output`, `on_retry`, `after_run` — exist so that any new guard (PlanReviewer-style "raw LLM verdict directly into pipeline state" being the original anti-pattern) lands as a `validate_output` override rather than as ad-hoc post-processing in a calling component. Without this closure, every caller invents its own retry policy, its own gate, its own logging — and bugs accumulate at every call site.

**How to apply:**
- One LLM call per agent attempt; at most two attempts per `Agent.run` (default `RetryPolicy.max_retries=1`).
- Schema-validation failure and semantic-validation failure share the same retry budget. Both count toward `attempts`.
- Failure surfaces as `AgentRunFailure(agent_name, attempts, reason)`, never as an exception — so the caller can choose a fallback without losing the trace.
- Per-agent gates plug in as `validate_input` / `validate_output` overrides; they MUST return `InputVerdict` / `OutputVerdict` (not bare booleans).
- The `inferencing` layer (`app/inferencing/*`) is the only place that calls the provider SDK. Anything else that imports `Anthropic` directly is a defect.

See also: Principle 4 (LLM as reviewer, not producer) — now enforced by the lifecycle, not by convention.
