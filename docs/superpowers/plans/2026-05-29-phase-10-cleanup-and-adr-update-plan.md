# Phase 10 — Cleanup + ADR Update

> **Scaffold plan.** Full bite-sized steps land after Phase 9 merges and v2 has been stable in production for one cycle.

**Goal:** Remove the deprecated v1 chain entirely. Update ADRs (`ADR-0008` canvas architecture, `ADR-0009` judge architecture) to reflect the plan-driven design as the canonical canvas architecture.

**Spec sections:** §11 phase 11.

**Depends on:** Phase 9 merged + at least one stable observation cycle.

---

## File map

**Delete:**
- `app/routers/extract_canvas_v1.py` (the rollback shim from Phase 9)
- `app/routers/extract_canvas_v2.py` (deprecated redirect from Phase 9)
- Any remaining Tier 4 extractor files not deleted in Phase 5
- Any remaining Tier 5 validator files not deleted in Phase 7
- Any remaining legacy judge files not deleted in Phase 8
- `app/components/workbook/canvas_reconciler.py` (row-grain shim; replaced by `CanvasApplier`)

**Modify:**
- `docs/adrs/ADR-0008-canvas-architecture.md` — append a "Superseded by plan-driven design" section pointing to the new spec
- `docs/adrs/ADR-0009-canvas-judge-architecture.md` — append a similar section
- `docs/adrs/` — write `ADR-0010-plan-driven-canvas-architecture.md` (the formal ADR for the new design)
- `ARCHITECTURE.md` — final cleanup pass; remove "v1 / v2" language now that there's only one chain

---

## Task outline

1. **Verify nothing imports the deletion candidates** — `grep -r "from app.components.extractors" app/` etc. — before deleting.
2. **Delete in dependency order** — routers first, then components, then helpers.
3. **Run full non-live suite** after each batch of deletions.
4. **Write `ADR-0010`** — references the spec at `docs/superpowers/specs/2026-05-29-plan-driven-canvas-architecture-design.md` as the canonical design source. Status: Accepted.
5. **Update older ADRs** with "Superseded by ADR-0010" notes.
6. **Final commit** closes the migration.

---

## Validation

- `make test` green.
- No file in `app/` imports any deleted module.
- ADR-0010 merged; ADR-0008 and ADR-0009 marked superseded.
- Architecture docs reference only the plan-driven chain.
