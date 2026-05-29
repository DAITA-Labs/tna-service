# Phase 1 — Enum Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land every enum the plan-driven canvas architecture will reference under a single import path (`app/enums/`), with zero downstream code changes for already-imported names.

**Architecture:** Add six new enums in `app/enums/` (one file each), move `PliAxis` from `app/specs/enums.py` to `app/enums/pli_axis.py` with a re-export shim, and re-export four other already-scattered enums (`FieldScope`, `ValueDtype`, `ValueDtypeMode`, `LabelMatchMode`) through `app/enums/__init__.py`. Existing imports keep working; new code uses `app/enums/`.

**Tech Stack:** Python 3.12, `enum.Enum` (str-mixin), pytest. No new dependencies.

**Spec section:** §4 ("Core types — Enum locations") and §11 phase 2 of `docs/superpowers/specs/2026-05-29-plan-driven-canvas-architecture-design.md`.

**Branch:** `canvas-plan-arch` (already created off `canvas-architecture`).

---

## File map

**Create:**
- `app/enums/field_location_mode.py` — `FieldLocationMode = {COLUMN, KV_BLOCK, MISSING}`
- `app/enums/stage_axis.py` — `StageAxis = {HORIZONTAL, VERTICAL, NONE}`
- `app/enums/subfield_axis.py` — `SubfieldAxis = {HORIZONTAL, IMPLICIT, NONE}`
- `app/enums/judge_decision.py` — `JudgeDecision = {APPROVE, MODIFY, ESCALATE}`
- `app/enums/policy_severity.py` — `PolicySeverity = {INFO, WARNING, ERROR}`
- `app/enums/cluster_role.py` — `ClusterRole = {PLI_CLUSTER, METADATA_ONLY, SUMMARY, OTHER}`
- `app/enums/pli_axis.py` — `PliAxis = {VERTICAL, SECTIONAL, SHEET}` (moved from `app/specs/enums.py`)
- `tests/unit/enums/test_new_enums.py` — value + identity coverage for all six new enums
- `tests/unit/enums/test_pli_axis_reexport.py` — covers the move + re-export shim
- `tests/unit/enums/test_aggregate_reexports.py` — covers the four `app/specs/enums.py` names re-exported through `app/enums/__init__.py`

**Modify:**
- `app/enums/__init__.py` — re-export every new enum + four legacy names
- `app/specs/enums.py` — replace the `PliAxis` class definition with `from app.enums.pli_axis import PliAxis` (keeps existing `app.specs.enums.PliAxis` imports working)

**Convention (no enforcement code in this phase):** new code under `app/policies/`, `app/components/pickers/`, `app/artifacts/plan.py`, `app/agents/judges/canvas_plan_reviewer/` MUST import from `app/enums/` and MUST NOT use inline `Literal[...]` types where an enum exists. Enforcement is left as future work; for Phase 1 it lives in code review.

---

## Task-by-task plan

Each new-enum task follows the same TDD shape. Task 1 lays out the full pattern; tasks 2–6 repeat it with the appropriate name/values (the code is shown in full per task — do not refer back to earlier tasks).

### Task 1: `FieldLocationMode`

**Files:**
- Create: `app/enums/field_location_mode.py`
- Test: `tests/unit/enums/test_new_enums.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/enums/test_new_enums.py` (create file with the imports below if it doesn't exist):

```python
"""Value + identity coverage for the new enums added in Phase 1."""
from __future__ import annotations


def test_field_location_mode_values() -> None:
    from app.enums.field_location_mode import FieldLocationMode

    assert {m.value for m in FieldLocationMode} == {"column", "kv_block", "missing"}
    assert FieldLocationMode.COLUMN.value    == "column"
    assert FieldLocationMode.KV_BLOCK.value  == "kv_block"
    assert FieldLocationMode.MISSING.value   == "missing"


def test_field_location_mode_is_str_enum() -> None:
    from app.enums.field_location_mode import FieldLocationMode

    assert isinstance(FieldLocationMode.COLUMN, str)
    assert FieldLocationMode.COLUMN == "column"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/enums/test_new_enums.py::test_field_location_mode_values -v`
Expected: `FAIL` with `ModuleNotFoundError: No module named 'app.enums.field_location_mode'`.

- [ ] **Step 3: Write the enum file**

Create `app/enums/field_location_mode.py`:

```python
"""FieldLocationMode — where a canonical field's value is read from."""
from __future__ import annotations

from enum import Enum


class FieldLocationMode(str, Enum):
    COLUMN   = "column"
    KV_BLOCK = "kv_block"
    MISSING  = "missing"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/enums/test_new_enums.py::test_field_location_mode_values tests/unit/enums/test_new_enums.py::test_field_location_mode_is_str_enum -v`
Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add app/enums/field_location_mode.py tests/unit/enums/test_new_enums.py
git commit -m "feat(enums): add FieldLocationMode

New enum for the plan-driven canvas architecture's FieldLocation
artifact. Values: COLUMN, KV_BLOCK, MISSING."
```

### Task 2: `StageAxis`

**Files:**
- Create: `app/enums/stage_axis.py`
- Test: `tests/unit/enums/test_new_enums.py` (append)

- [ ] **Step 1: Append the failing test**

Add to `tests/unit/enums/test_new_enums.py`:

```python
def test_stage_axis_values() -> None:
    from app.enums.stage_axis import StageAxis

    assert {m.value for m in StageAxis} == {"horizontal", "vertical", "none"}
    assert StageAxis.HORIZONTAL.value == "horizontal"
    assert StageAxis.VERTICAL.value   == "vertical"
    assert StageAxis.NONE.value       == "none"


def test_stage_axis_is_str_enum() -> None:
    from app.enums.stage_axis import StageAxis

    assert isinstance(StageAxis.HORIZONTAL, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/enums/test_new_enums.py::test_stage_axis_values -v`
Expected: `FAIL` with `ModuleNotFoundError: No module named 'app.enums.stage_axis'`.

- [ ] **Step 3: Write the enum file**

Create `app/enums/stage_axis.py`:

```python
"""StageAxis — how stage bands lay out across the canvas."""
from __future__ import annotations

from enum import Enum


class StageAxis(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL   = "vertical"
    NONE       = "none"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/enums/test_new_enums.py::test_stage_axis_values tests/unit/enums/test_new_enums.py::test_stage_axis_is_str_enum -v`
Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add app/enums/stage_axis.py tests/unit/enums/test_new_enums.py
git commit -m "feat(enums): add StageAxis

Stage band axis enum for CanvasPlan: HORIZONTAL / VERTICAL / NONE."
```

### Task 3: `SubfieldAxis`

**Files:**
- Create: `app/enums/subfield_axis.py`
- Test: `tests/unit/enums/test_new_enums.py` (append)

- [ ] **Step 1: Append the failing test**

Add to `tests/unit/enums/test_new_enums.py`:

```python
def test_subfield_axis_values() -> None:
    from app.enums.subfield_axis import SubfieldAxis

    assert {m.value for m in SubfieldAxis} == {"horizontal", "implicit", "none"}
    assert SubfieldAxis.HORIZONTAL.value == "horizontal"
    assert SubfieldAxis.IMPLICIT.value   == "implicit"
    assert SubfieldAxis.NONE.value       == "none"


def test_subfield_axis_is_str_enum() -> None:
    from app.enums.subfield_axis import SubfieldAxis

    assert isinstance(SubfieldAxis.HORIZONTAL, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/enums/test_new_enums.py::test_subfield_axis_values -v`
Expected: `FAIL` with `ModuleNotFoundError: No module named 'app.enums.subfield_axis'`.

- [ ] **Step 3: Write the enum file**

Create `app/enums/subfield_axis.py`:

```python
"""SubfieldAxis — how a stage's subfields (planned/actual/etc.) lay out."""
from __future__ import annotations

from enum import Enum


class SubfieldAxis(str, Enum):
    HORIZONTAL = "horizontal"
    IMPLICIT   = "implicit"
    NONE       = "none"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/enums/test_new_enums.py::test_subfield_axis_values tests/unit/enums/test_new_enums.py::test_subfield_axis_is_str_enum -v`
Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add app/enums/subfield_axis.py tests/unit/enums/test_new_enums.py
git commit -m "feat(enums): add SubfieldAxis

Subfield axis enum for stage bands: HORIZONTAL / IMPLICIT / NONE."
```

### Task 4: `JudgeDecision`

**Files:**
- Create: `app/enums/judge_decision.py`
- Test: `tests/unit/enums/test_new_enums.py` (append)

- [ ] **Step 1: Append the failing test**

Add to `tests/unit/enums/test_new_enums.py`:

```python
def test_judge_decision_values() -> None:
    from app.enums.judge_decision import JudgeDecision

    assert {m.value for m in JudgeDecision} == {"approve", "modify", "escalate"}
    assert JudgeDecision.APPROVE.value  == "approve"
    assert JudgeDecision.MODIFY.value   == "modify"
    assert JudgeDecision.ESCALATE.value == "escalate"


def test_judge_decision_is_str_enum() -> None:
    from app.enums.judge_decision import JudgeDecision

    assert isinstance(JudgeDecision.APPROVE, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/enums/test_new_enums.py::test_judge_decision_values -v`
Expected: `FAIL` with `ModuleNotFoundError: No module named 'app.enums.judge_decision'`.

- [ ] **Step 3: Write the enum file**

Create `app/enums/judge_decision.py`:

```python
"""JudgeDecision — terminal decision emitted by CanvasPlanReviewer."""
from __future__ import annotations

from enum import Enum


class JudgeDecision(str, Enum):
    APPROVE  = "approve"
    MODIFY   = "modify"
    ESCALATE = "escalate"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/enums/test_new_enums.py::test_judge_decision_values tests/unit/enums/test_new_enums.py::test_judge_decision_is_str_enum -v`
Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add app/enums/judge_decision.py tests/unit/enums/test_new_enums.py
git commit -m "feat(enums): add JudgeDecision

Top-level verdict outcome for the canvas plan reviewer judge:
APPROVE / MODIFY / ESCALATE."
```

### Task 5: `PolicySeverity`

**Files:**
- Create: `app/enums/policy_severity.py`
- Test: `tests/unit/enums/test_new_enums.py` (append)

- [ ] **Step 1: Append the failing test**

Add to `tests/unit/enums/test_new_enums.py`:

```python
def test_policy_severity_values() -> None:
    from app.enums.policy_severity import PolicySeverity

    assert {m.value for m in PolicySeverity} == {"info", "warning", "error"}
    assert PolicySeverity.INFO.value    == "info"
    assert PolicySeverity.WARNING.value == "warning"
    assert PolicySeverity.ERROR.value   == "error"


def test_policy_severity_is_str_enum() -> None:
    from app.enums.policy_severity import PolicySeverity

    assert isinstance(PolicySeverity.INFO, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/enums/test_new_enums.py::test_policy_severity_values -v`
Expected: `FAIL` with `ModuleNotFoundError: No module named 'app.enums.policy_severity'`.

- [ ] **Step 3: Write the enum file**

Create `app/enums/policy_severity.py`:

```python
"""PolicySeverity — optional severity tag a policy may attach to its verdict."""
from __future__ import annotations

from enum import Enum


class PolicySeverity(str, Enum):
    INFO    = "info"
    WARNING = "warning"
    ERROR   = "error"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/enums/test_new_enums.py::test_policy_severity_values tests/unit/enums/test_new_enums.py::test_policy_severity_is_str_enum -v`
Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add app/enums/policy_severity.py tests/unit/enums/test_new_enums.py
git commit -m "feat(enums): add PolicySeverity

Severity tag for PolicyVerdict (optional): INFO / WARNING / ERROR."
```

### Task 6: `ClusterRole`

**Files:**
- Create: `app/enums/cluster_role.py`
- Test: `tests/unit/enums/test_new_enums.py` (append)

- [ ] **Step 1: Append the failing test**

Add to `tests/unit/enums/test_new_enums.py`:

```python
def test_cluster_role_values() -> None:
    from app.enums.cluster_role import ClusterRole

    assert {m.value for m in ClusterRole} == {
        "pli_cluster", "metadata_only", "summary", "other",
    }
    assert ClusterRole.PLI_CLUSTER.value   == "pli_cluster"
    assert ClusterRole.METADATA_ONLY.value == "metadata_only"
    assert ClusterRole.SUMMARY.value       == "summary"
    assert ClusterRole.OTHER.value         == "other"


def test_cluster_role_is_str_enum() -> None:
    from app.enums.cluster_role import ClusterRole

    assert isinstance(ClusterRole.PLI_CLUSTER, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/enums/test_new_enums.py::test_cluster_role_values -v`
Expected: `FAIL` with `ModuleNotFoundError: No module named 'app.enums.cluster_role'`.

- [ ] **Step 3: Write the enum file**

Create `app/enums/cluster_role.py`:

```python
"""ClusterRole — semantic role of a workbook cluster after classification."""
from __future__ import annotations

from enum import Enum


class ClusterRole(str, Enum):
    PLI_CLUSTER    = "pli_cluster"
    METADATA_ONLY  = "metadata_only"
    SUMMARY        = "summary"
    OTHER          = "other"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/enums/test_new_enums.py::test_cluster_role_values tests/unit/enums/test_new_enums.py::test_cluster_role_is_str_enum -v`
Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add app/enums/cluster_role.py tests/unit/enums/test_new_enums.py
git commit -m "feat(enums): add ClusterRole

Cluster classification outcome enum:
PLI_CLUSTER / METADATA_ONLY / SUMMARY / OTHER."
```

### Task 7: Move `PliAxis` to `app/enums/pli_axis.py` (with shim)

`PliAxis` currently lives in `app/specs/enums.py`. The spec puts it in `app/enums/`. Move the class definition there and replace the class in `app/specs/enums.py` with a re-export so existing imports (`from app.specs.enums import PliAxis`) keep working.

**Files:**
- Create: `app/enums/pli_axis.py`
- Modify: `app/specs/enums.py` (replace `class PliAxis(...)` block with re-export)
- Test: `tests/unit/enums/test_pli_axis_reexport.py`

- [ ] **Step 1: Read the current `PliAxis` definition**

Run: `sed -n '29,46p' app/specs/enums.py`
Capture the exact value set — Phase 1 must preserve it byte-for-byte (spec §4 names `{VERTICAL, SECTIONAL, SHEET}` but if the existing class uses other casings or value strings, the new module mirrors what's already in production; we do NOT rename values here).

- [ ] **Step 2: Write the failing test**

Create `tests/unit/enums/test_pli_axis_reexport.py`:

```python
"""PliAxis was moved to app/enums/; legacy imports must still work."""
from __future__ import annotations


def test_pli_axis_importable_from_enums() -> None:
    from app.enums.pli_axis import PliAxis
    assert hasattr(PliAxis, "VERTICAL")
    assert hasattr(PliAxis, "SECTIONAL")
    assert hasattr(PliAxis, "SHEET")


def test_pli_axis_legacy_import_path_preserved() -> None:
    from app.enums.pli_axis import PliAxis as Canonical
    from app.specs.enums import PliAxis as Legacy
    assert Canonical is Legacy
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/enums/test_pli_axis_reexport.py -v`
Expected: `FAIL` on `test_pli_axis_importable_from_enums` with `ModuleNotFoundError: No module named 'app.enums.pli_axis'`.

- [ ] **Step 4: Create `app/enums/pli_axis.py` with the moved class**

Use the exact value set captured in Step 1. The expected shape, per spec §4 and the existing `app/specs/enums.py:29`:

```python
"""PliAxis — how PLIs lay out across a bundle's anchor sheet."""
from __future__ import annotations

from enum import Enum


class PliAxis(str, Enum):
    VERTICAL  = "vertical"
    SECTIONAL = "sectional"
    SHEET     = "sheet"
```

If the captured definition uses different values, paste those instead — do not change them in this task.

- [ ] **Step 5: Replace the class in `app/specs/enums.py` with a re-export**

In `app/specs/enums.py`, locate the `class PliAxis(...)` block (starts at line 29 per current state). Replace the entire class body with:

```python
# Moved to app/enums/pli_axis.py; re-exported here for backward compatibility.
from app.enums.pli_axis import PliAxis  # noqa: F401
```

Make sure no other line in `app/specs/enums.py` re-defines `PliAxis`.

- [ ] **Step 6: Run the test to verify both imports give the same class**

Run: `pytest tests/unit/enums/test_pli_axis_reexport.py -v`
Expected: both tests pass.

- [ ] **Step 7: Run the full non-live suite to catch any consumer that relied on the class body location**

Run: `pytest tests -q -m "not live"`
Expected: all tests pass. If a test fails because of a circular import between `app/specs/enums.py` and `app/enums/pli_axis.py`, the fix is to ensure `app/enums/pli_axis.py` imports only from the stdlib (it already does in the snippet above).

- [ ] **Step 8: Commit**

```bash
git add app/enums/pli_axis.py app/specs/enums.py tests/unit/enums/test_pli_axis_reexport.py
git commit -m "refactor(enums): move PliAxis to app/enums/ with backward-compat shim

The plan-driven canvas architecture (§4) anchors every enum under
app/enums/. PliAxis was the only listed enum already living elsewhere;
move it and keep a re-export in app/specs/enums.py so existing imports
keep working."
```

### Task 8: Re-export legacy `app/specs/enums.py` names through `app/enums/__init__.py`

Spec §4 says `FieldScope`, `ValueDtype`, `ValueDtypeMode`, `LabelMatchMode` stay in `app/specs/enums.py` but become reachable through `app/enums/` for a single import path.

**Files:**
- Modify: `app/enums/__init__.py`
- Test: `tests/unit/enums/test_aggregate_reexports.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/enums/test_aggregate_reexports.py`:

```python
"""Single-import-path coverage for app/enums/."""
from __future__ import annotations


def test_field_scope_reexported() -> None:
    from app.enums import FieldScope as Reexp
    from app.specs.enums import FieldScope as Canonical
    assert Reexp is Canonical


def test_value_dtype_reexported() -> None:
    from app.enums import ValueDtype as Reexp
    from app.specs.enums import ValueDtype as Canonical
    assert Reexp is Canonical


def test_value_dtype_mode_reexported() -> None:
    from app.enums import ValueDtypeMode as Reexp
    from app.specs.enums import ValueDtypeMode as Canonical
    assert Reexp is Canonical


def test_label_match_mode_reexported() -> None:
    from app.enums import LabelMatchMode as Reexp
    from app.specs.enums import LabelMatchMode as Canonical
    assert Reexp is Canonical


def test_new_enums_reexported_from_package() -> None:
    """Every new enum from Task 1-7 is reachable via `from app.enums import …`."""
    from app.enums import (
        FieldLocationMode,
        StageAxis,
        SubfieldAxis,
        JudgeDecision,
        PolicySeverity,
        ClusterRole,
        PliAxis,
    )
    assert FieldLocationMode.COLUMN.value == "column"
    assert StageAxis.HORIZONTAL.value     == "horizontal"
    assert SubfieldAxis.IMPLICIT.value    == "implicit"
    assert JudgeDecision.APPROVE.value    == "approve"
    assert PolicySeverity.WARNING.value   == "warning"
    assert ClusterRole.PLI_CLUSTER.value  == "pli_cluster"
    assert PliAxis.VERTICAL.value         == "vertical"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/enums/test_aggregate_reexports.py -v`
Expected: `FAIL` on the first `is` assertion (or on `ImportError: cannot import name 'FieldScope' from 'app.enums'`).

- [ ] **Step 3: Update `app/enums/__init__.py`**

Read the current contents first with `cat app/enums/__init__.py`. Then write the file to re-export everything:

```python
"""app.enums — single import path for the project's enums.

New code MUST import every enum from this package. Legacy modules
(`app/specs/enums.py`) keep working via re-exports below.
"""
from __future__ import annotations

# New enums added in Phase 1 of the plan-driven canvas architecture.
from app.enums.cluster_role           import ClusterRole
from app.enums.field_location_mode    import FieldLocationMode
from app.enums.judge_decision         import JudgeDecision
from app.enums.pli_axis               import PliAxis
from app.enums.policy_severity        import PolicySeverity
from app.enums.stage_axis             import StageAxis
from app.enums.subfield_axis          import SubfieldAxis

# Existing app/enums/ modules — re-export their classes here so the
# single-import-path rule holds for everything.
from app.enums.cell_dtype             import CellDtype
from app.enums.environment            import Environment
from app.enums.location_pattern       import LocationPattern
from app.enums.pli_mode               import PliMode
from app.enums.row_role               import RowRole
from app.enums.stage_scope            import StageScope
from app.enums.validation_severity    import ValidationSeverity

# Legacy enums still housed in app/specs/enums.py — re-export for a
# single import path. (Phase 1 spec §4: "New code imports from
# app/enums/; existing imports keep working via re-export.")
from app.specs.enums import (
    FieldScope,
    LabelMatchMode,
    ValueDtype,
    ValueDtypeMode,
)

__all__ = [
    # Phase-1 new
    "ClusterRole",
    "FieldLocationMode",
    "JudgeDecision",
    "PliAxis",
    "PolicySeverity",
    "StageAxis",
    "SubfieldAxis",
    # Existing app/enums/
    "CellDtype",
    "Environment",
    "LocationPattern",
    "PliMode",
    "RowRole",
    "StageScope",
    "ValidationSeverity",
    # Legacy specs/enums re-exports
    "FieldScope",
    "LabelMatchMode",
    "ValueDtype",
    "ValueDtypeMode",
]
```

Before saving, verify each `from app.enums.<module> import <Name>` line matches an actual class in that file (`grep -l "^class" app/enums/*.py`). If one of the existing app/enums files exposes a class with a different name (e.g. legacy naming), drop that re-export from this file and note it in the commit message rather than renaming.

- [ ] **Step 4: Run the new test file**

Run: `pytest tests/unit/enums/test_aggregate_reexports.py -v`
Expected: all five tests pass.

- [ ] **Step 5: Run the full non-live suite**

Run: `pytest tests -q -m "not live"`
Expected: all tests pass (the re-export must not have introduced a circular import; if it does, the loop is between `app/enums/__init__.py` and `app/specs/enums.py`, fix by deferring the `from app.specs.enums import …` line to a `TYPE_CHECKING` block — but try the eager import first since `app/specs/enums.py` does not import from `app/enums/`).

- [ ] **Step 6: Commit**

```bash
git add app/enums/__init__.py tests/unit/enums/test_aggregate_reexports.py
git commit -m "feat(enums): single import path for all project enums

Re-export Phase-1 new enums, existing app/enums/ enums, and the
four legacy app/specs/enums.py names through app/enums/__init__.py.
New canvas-plan-arch code imports from app/enums/ only; legacy code
keeps its existing imports."
```

### Task 9: Document the convention in `app/enums/__init__.py` and the spec

The module docstring written in Task 8 already states the rule for human readers. Add one more pointer so future contributors hit it from the architecture doc.

**Files:**
- Modify: `ARCHITECTURE.md` (add one bullet under the "Conventions" or equivalent section)

- [ ] **Step 1: Find the right place in ARCHITECTURE.md**

Run: `grep -n -i "convention\|coding standard\|import\|enum" ARCHITECTURE.md | head -20`
Expected: pick a section that lists project-wide conventions. If none exists, add a "Conventions" section at the bottom.

- [ ] **Step 2: Add the convention bullet**

Append (or insert into the located section):

```markdown
- **Enums live in `app/enums/`** — one file per enum, alphabetically ordered. New code MUST import from `app/enums/` (the package re-exports everything, including legacy enums still defined in `app/specs/enums.py`). Inline `Literal[...]` types are not used where an enum exists. See `app/enums/__init__.py` for the canonical list.
```

- [ ] **Step 3: Commit**

```bash
git add ARCHITECTURE.md
git commit -m "docs(arch): document app/enums single-import-path convention"
```

### Task 10: Final guard — run full non-live suite + push

- [ ] **Step 1: Run the full non-live test suite**

Run: `make test`
Expected: all tests pass. Test count goes up by exactly the count added in Tasks 1-8 (14 tests; six `*_values` + six `*_is_str_enum` from Tasks 1-6, two from Task 7, five from Task 8 — minus any that fold into the same parametrized case if you reshaped).

- [ ] **Step 2: Push the branch**

Run: `git push origin canvas-plan-arch`
Expected: branch updated on remote; no PR opened (the next plan continues on the same branch).

---

## Self-review

**Spec coverage:** §4 lists seven new enum modules (`FieldLocationMode`, `PliAxis`, `StageAxis`, `SubfieldAxis`, `JudgeDecision`, `PolicySeverity`, `ClusterRole`) and four re-exports (`FieldScope`, `ValueDtype`, `ValueDtypeMode`, `LabelMatchMode`). Tasks 1-8 cover all eleven. The "new code imports from `app/enums/`; existing imports keep working" rule is covered by Task 7's shim + Task 8's `__init__.py` re-export. The "no inline `Literal[...]` in new code" rule is captured as a convention bullet in Task 9, with enforcement left to code review (deliberate YAGNI — no lint rule needed before any new-shape code lands).

**Placeholder scan:** every code block is concrete; no `TBD`, no "similar to Task N". Each task repeats its own code.

**Type consistency:** every enum name and value casing matches §4 of the spec. `PliAxis` values (`"vertical"`, `"sectional"`, `"sheet"`) match the spec; Step 1 of Task 7 explicitly captures the live values first so if the live class drifts from the spec, the live values win and the spec drift becomes a separate ticket (out of scope for Phase 1).

**Scope check:** this plan adds enums only — no policy code, no picker code, no judge code. It is a strict prerequisite for Phase 2 (picker base) and can ship as a standalone commit run.

---

## Execution handoff

Phase 1 is the foundation. Recommended approach: **Subagent-Driven Development** — fresh subagent per task, two-stage review per task (spec compliance, then code quality). Each enum task is small (~5 minutes), so the per-task review overhead is the dominant cost — but each subagent gets full code context here in this plan.

Alternative: **Inline Execution** — fast for ten tiny TDD cycles, no review overhead, single session.
