# 0002 — Faithful extraction

**Date:** 2026-05-09
**Status:** Accepted

## Context

During the M0 single-prompt baseline run against `20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx`, the model split `style_code` at the first numeric token:

- Cell contains: `"890162 TAVIRA_2 522148"`
- Model emitted: `style_code = "890162"`, `style_name = "TAVIRA_2 522148"` (cross-PLI copy errors also appeared)

This produced 71% field precision/recall. The model was also embedding per-field confidence objects (`{value, confidence}`) despite the tool schema expecting flat values, causing 24 Pydantic validation errors.

Additionally, stage columns caused confusion: `"Sewing Start"` + `"Sewing End"` were emitted as two separate stages instead of one `"Sewing"` stage with sub-fields, even when explicitly prompted otherwise. Non-milestone PLI-level fields (`"Original Order Received"`, `"Order L/D"`, etc.) were being emitted as stages.

## Decision

Establish the faithful extraction principle as a load-bearing rule for all extraction code and prompts:

1. A cell's content IS the field value. Copy verbatim.
2. One cell → one field. No splitting, no concatenating.
3. Null over fabrication. Fields you can't find are null; add a Warning.
4. Two PLIs may share the same `io_number` (one buyer PO can produce multiple style/color combinations). Never dedupe by `io_number`.

Stage canonicalization rule: when multiple columns/rows describe one logical stage (`"Sewing Start"`, `"Sewing End"`, `"Sewing Plan"`, `"Sewing Actual"`, `"Sewing Approved"`), they form one stage. The root word (`"Sewing"`) is the canonical name. The "Start"/"Plan" date is `planned_date`; all other sub-fields go in `stage.metadata`.

A separate `PLI.metadata: dict[str, Any]` field holds non-canonical PLI-level extracted fields — admin/lifecycle context (order dates, lead-times) that are not production milestones.

Rewriting the baseline system prompt to encode these rules recovered field precision/recall from 71% → 100% on the DKN benchmark.

## Consequences

**Easier:**
- Downstream consumers receive exactly what the buyer entered; no silent normalisation.
- Eval scoring is straightforward: compare verbatim strings, no fuzzy matching.
- Duplicate `io_number` values across PLIs are valid and round-trip correctly through the eval harness.

**Harder / constrained:**
- Stage canonicalization still requires an LLM specialist (`StageLocator` → `FieldNamer`) because rule-based canonicalization is brittle across supplier vocabulary.
- Implementing faithful extraction in prompts doesn't eliminate the stage-canonicalization miss in the single-prompt baseline (83% stage recall persisted). This is a known limitation of the single-prompt approach; the multi-agent split (ADR-0001) is the fix.

**What we gave up:**
- Convenient normalisation (auto-trimming whitespace, canonical casing). These must be done downstream if needed, not in the parser.

## Alternatives considered

- **Normalise during extraction** (trim whitespace, standardise case, split compound codes). Rejected: destroys auditability; the buyer-entered string is legally meaningful in some contexts; normalisation rules vary by supplier.
- **Allow LLM to infer canonical field names from cell content.** Rejected: leads to hallucination of values not present in the cell. The `FieldNamer` agent maps *labels* (column headers) to canonical names, not cell values.
