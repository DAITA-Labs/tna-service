# Phase 8 — CanvasPlanReviewer Judge + Tool Set

> **Scaffold plan.** Full bite-sized steps land after Phase 7 merges. Judge integration is the most novel piece; expect this scaffold to grow significantly at expansion time.

**Goal:** Replace the existing per-finding / phase judges (PR #80-#83) with a single `CanvasPlanReviewer` agent that reviews the assembled `CanvasPlan` and a compact verdict trail, with bounded peek access into the underlying canvas via a tool set.

**Architecture:** Haystack `Agent` component (per spec §10.1) wraps an Anthropic chat generator + a tool list. One tool is the **terminator** (`submit_plan_review_verdict`) whose input schema IS the `PlanReviewVerdict` Pydantic model. The agent's loop ends when this tool is called; the gate component validates the input and applies the verdict.

**Spec sections:** §10 (judge integration), §10.1 (Haystack Agent runtime).

**Depends on:** Phase 7 merged.

---

## File map

**Create:**
- `app/tools/judges/` — new tool module:
  - `peek_range.py` — bounded sheet peek (max 20 rows × 10 cols)
  - `get_column_profile.py`
  - `get_row_profile.py`
  - `get_strips_at.py`
  - `get_merge_spans_in.py`
  - `get_kv_blocks_near.py`
  - `submit_plan_review_verdict.py` — the terminator tool; input schema = `PlanReviewVerdict`
- `app/agents/judges/canvas_plan_reviewer/` — `agent.py`, `schema.py` (`PlanReviewVerdict`), `prompt.py`
- `app/components/judges/canvas_plan_reviewer_gate.py` — wraps the Haystack `Agent`; trigger logic + verdict application
- `app/prompts/judges/canvas_plan_reviewer.py` — system prompt

**Retire (after parity):**
- `app/agents/judges/identifier_finding/` and `app/agents/judges/identifier_phase/`
- `app/agents/judges/stage_finding/` and `app/agents/judges/stage_phase/`
- `app/agents/judges/metadata/`
- `app/components/judges/identifier_finding_gate.py`, `identifier_phase_gate.py`, `stage_finding_gate.py`, `stage_phase_gate.py`, `metadata_gate.py`
- `app/pipelines/canvas_judges.py`

**Modify:**
- `app/pipelines/extract_canvas_v2.py` — replace the legacy judge pipeline with `CanvasPlanReviewerGate`
- `app/tools/__init__.py` — register every new judge tool in `TOOL_REGISTRY`

---

## Task outline

1. **`PlanReviewVerdict` Pydantic schema** — top-level decision (`JudgeDecision` enum from Phase 1) + optional `modify` payload + reason.
2. **The six peek/profile tools** — each is a `@tool`-decorated function with hard per-call limits enforced in the function body.
3. **`submit_plan_review_verdict` terminator tool** — input schema = `PlanReviewVerdict`; the tool body just returns its input (Haystack `Agent` records the call; the gate extracts the input).
4. **System prompt** — instructs the agent: gather evidence with peek/profile tools, then call `submit_plan_review_verdict` exactly once.
5. **`build_canvas_plan_reviewer(...)` factory** — per spec §10.1.
6. **`CanvasPlanReviewerGate` component** — trigger logic (only invoke when verdict trail has policy eliminations or warnings), agent invocation, verdict application (apply / re-pick / escalate).
7. **Live test** — one xlsx fixture, real Anthropic key (gated on `live` marker), assert the agent terminates inside `max_agent_steps`.
8. **Delete legacy judges** after parity confirmed on the canvas eval.

---

## Validation

- Canvas eval results match or beat the legacy judge chain.
- `CanvasPlanReviewer` terminates inside `max_agent_steps=10` on every labelled family.
- Average peek-tool calls per invocation under 3 on the dataset.
- Total judge token spend per invocation under 5000 tokens p95.
