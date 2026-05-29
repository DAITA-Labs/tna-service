# Phase 4 — Migrate Tier 3 Workbook Routing to Pickers

> **Scaffold plan.** Full bite-sized steps land after Phase 3 merges.

**Goal:** Convert `Profiler`, `Clusterer`, `RoleClassifier`, and `AnchorPicker` from imperative resolvers into the picker pattern. Cluster-role assignment becomes a `ClusterRolePicker` whose policies consume the new `ClusterRole` enum from Phase 1.

**Architecture:** Workbook phase ends up as a chain of pickers identical in shape to the structure phase. `ClusterAnchorBundle` artifact unchanged.

**Spec sections:** §3 layer 2 (Workbook), §9 layer 2 picker list.

**Depends on:** Phase 3 merged.

---

## File map

**Create:**
- `app/components/pickers/cluster_role_picker.py` + `app/policies/workbook/cluster_role.py`
- `app/components/pickers/anchor_sheet_workbook_picker.py` + `app/policies/workbook/anchor_sheet.py`
- `app/components/pickers/profile_band_picker.py` + `app/policies/workbook/profile_band.py`

**Migrate:**
- `app/components/workbook/role_classifier.py` → `cluster_role_picker.py`
- `app/components/workbook/anchor_picker.py` → `anchor_sheet_workbook_picker.py`
- `app/components/workbook/profiler.py` and `clusterer.py` — keep candidate generation, move scoring/eliminations into policies

**Modify:**
- `app/pipelines/workbook_phase.py` — swap classifier component for picker

---

## Task outline

1. `ClusterRolePicker` first — small, well-bounded decision; validates the picker shape on workbook-level data.
2. `AnchorSheetWorkbookPicker` next.
3. `ProfileBandPicker` last — has the most candidate generation work.
4. Per-picker A/B canvas-eval regression check.

---

## Validation

- Workbook phase tests green.
- Cluster-role outputs unchanged on every labelled family.
