# Coding Standard

**Status:** Draft v1
**Scope:** Python 3.12+. Portable across repos.

## 0. Intent

This document sets the surface-quality bar for Python code: naming, function
shape, docstrings, comments, types, errors, imports, module layout, and test
seams. The goal is code that a stranger — human or AI — can read once and trust.

**How to apply.** A subagent editing a file runs Section 10 against it before
commit. A human reviewer spot-checks Sections 1–9. Sections 1–9 are the rules;
Section 10 is their operational form.

**Precedence.** When this document conflicts with an explicit user instruction
or with `CLAUDE.md`, the user instruction or `CLAUDE.md` wins. When two rules
here seem to conflict, the more specific section wins.

**Amendment policy.** This standard is locked once approved. During a rollout,
subagents flag ambiguity in the commit report and use the most defensible
interpretation; they never amend mid-rollout. Amendments happen between phases.

## 1. Naming

Names are the first layer of documentation. A reader should be able to predict
what a function does from its name alone. Concise beats descriptive; descriptive
beats clever.

**Rules:**
- Use verb-first names for functions: `extract_pli`, `read_row`, `validate_invariants`. Not `pli_extractor`, `row_reader`.
- Use noun-first names for classes: `SheetPlanner`, `WorkbookCtx`, `AgentRunner`. Not `PlanSheets`, `ContextForWorkbook`.
- Prefix private helpers with a single underscore: `_coerce`, `_read_with_merge`.
- Match the domain vocabulary already used in this repo (`PLI`, `Stage`, `ANCHOR`, `CHILD`). Don't paraphrase domain terms.
- Single-letter names are allowed only for tightly-scoped loop variables (`for i in range(n)`, `for c in row`). Never for module-level helpers.
- No version suffixes (`process_v2`), no generic `_helper`/`_util` in names, no abbreviations a newcomer wouldn't recognise (`mgr`, `cfg` are fine; `pcl_xfm` is not).

**Example (from `plan_invariants.py`):**
```python
# Before — saves four characters at the cost of readability at every call site
def _e(check: str, msg: str) -> ValidationFinding: ...
def _w(check: str, msg: str) -> ValidationFinding: ...

# After
def _error(check: str, msg: str) -> ValidationFinding: ...
def _warn(check: str, msg: str) -> ValidationFinding: ...
```

**Checklist:**
- [ ] Functions are verb-first; classes are noun-first.
- [ ] Private helpers have a leading `_`; nothing public does.
- [ ] No version suffixes (`_v2`), no `_helper`/`_util` filler.
- [ ] No single-letter names outside tight loops.
- [ ] Domain vocabulary matches the rest of the codebase.

## 2. Functions

A function should do one nameable thing. Length is a proxy for that; the real
test is whether you can name the function and its helpers in concrete domain
terms. If the only honest helper name is `_part_two`, leave the function alone.

**Rules:**
- Soft length target: 40 lines in the body. Override with `# allow-long: <reason>` directly above the `def`, used sparingly.
- One job per function. When a function does N distinct things, extract N named helpers and have the original orchestrate.
- Prefer pure functions. When mutation is required, name the function so the reader expects it (`_apply_*`, `_record_*`, `_register_*`).
- Decomposition heuristic: if helpers can be named in domain terms, extract. If they can only be named structurally (`_first_loop`), don't.
- Don't over-decompose. A 10-line function that reads top-to-bottom is better than three 3-line helpers.

**Example (real, from `plan_invariants.py`):**
```python
# Before — one 55-line function running four distinct invariant checks inline
def validate_invariants(plan: SheetPlan) -> list[ValidationFinding]:
    out: list[ValidationFinding] = []
    # ... reference integrity (10 lines) ...
    # ... row uniqueness (5 lines) ...
    # ... header contiguity (10 lines) ...
    # ... pli block non-overlap (8 lines) ...
    # ... sub-row consistency (7 lines) ...
    # ... logging ...
    return out

# After — orchestrator + named helpers, each ~10 lines
def validate_invariants(plan: SheetPlan) -> list[ValidationFinding]:
    """Return all structural-invariant findings for `plan`."""
    findings: list[ValidationFinding] = []
    findings.extend(_check_reference_integrity(plan))
    findings.extend(_check_row_uniqueness(plan))
    findings.extend(_check_header_contiguity(plan))
    findings.extend(_check_pli_block_non_overlap(plan))
    findings.extend(_check_sub_row_consistency(plan))
    _log_if_findings(plan, findings)
    return findings
```

**Checklist:**
- [ ] No function body exceeds 40 lines without `# allow-long: <reason>`.
- [ ] Every function does one thing nameable in domain terms.
- [ ] Extracted helpers have concrete names, not structural ones (`_part_two`).
- [ ] No hidden mutation in functions whose name implies purity.

## 3. Docstrings

Docstrings exist to tell the reader what a function or module promises,
without making them read the body. They are not signature restatements. When
the signature already tells the story, the summary line is enough.

**Rules:**
- Required on every public function (no leading `_`), every class, and every module.
- Required on private functions longer than 10 lines or with non-obvious behaviour.
- Format: one-line summary in imperative mood (≤80 chars), ending with a period. If `Args/Returns/Raises` add information the signature doesn't, add a blank line and then those sections in plain prose.
- Module docstring: one paragraph stating the module's responsibility.
- Class docstring: one sentence stating the invariant the class promises (what an instance of this class guarantees).
- Use `"""triple double-quotes"""`. Never restate the signature in prose.

**Example:**
```python
# Before — from apply_plan.py: untyped, undocumented, non-obvious behaviour
def _coerce(field: str, val):
    if field in _STRING_FIELDS and val is not None:
        return str(val)
    return val

# After — types + a docstring that explains *why*, not what
def _coerce(field: str, val: object) -> object:
    """Coerce a raw cell value to the type expected by `field`.

    String-typed PLI fields (style_code, color_code) are stringified even
    when the cell holds an int — Excel sometimes stores codes as numbers.
    """
    if field in _STRING_FIELDS and val is not None:
        return str(val)
    return val
```

For functions whose signature already tells the story, a one-line summary is
enough: `"""Read every non-empty cell in `row` within [col_range] inclusive."""`

**Checklist:**
- [ ] Every public function, class, and module has a docstring.
- [ ] Private functions >10 lines or with non-obvious behaviour have one too.
- [ ] Summary lines are ≤80 chars, imperative mood, end in a period.
- [ ] `Args/Returns/Raises` appear only when they add information beyond the signature.
- [ ] No docstring restates the signature in prose.

## 4. Comments

Good comments explain why — a constraint, a surprise, a workaround, a spec
reference. Bad comments narrate what a well-named identifier already says.

**Rules:**
- Comment when explaining a non-obvious constraint, a surprising workaround, an off-by-one, or a reference to an external spec or issue.
- Don't narrate what the next line does. `x = x + 1  # increment x` is noise.
- Never reference plan-task names in code. `# SRP Task 17` or `# MA Task 12` is a defect; describe what the code does, not its commit lineage.
- Block comments above a function should be a docstring instead.
- Inline tactical notes are fine when terse: `# 1-based, not 0-based`, `# back-compat shim — delete after v2`.

**Example:**
```python
# Before — narrates what the code already says
# Loop over the rows and check each one
for row in plan.rows:
    # If the row is an anchor, add it to the anchor set
    if row.role is RowRole.ANCHOR:
        anchors.add(row.idx)

# After — no comment needed; the comprehension reads itself
anchors = {r.idx for r in plan.rows if r.role is RowRole.ANCHOR}

# Good — explains a real constraint (from tracing.py)
endpoint = (otlp_endpoint
            or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
            or os.environ.get("TEMPO_OTLP_ENDPOINT")  # back-compat during SigNoz migration
            or "http://otel-collector:4317")
```

**Checklist:**
- [ ] No comment narrates what a well-named identifier already says.
- [ ] No plan-task names in any comment or docstring.
- [ ] Comments above functions are docstrings, not block comments.
- [ ] Surviving inline comments explain a constraint, a workaround, or an external reference.

## 5. Type hints

Type hints are part of the API surface. They tell the reader and the type
checker what a function accepts and returns. Modern syntax keeps the code
short and avoids needless `typing` imports.

**Rules:**
- Every public function signature has parameter and return type hints.
- Modern built-in generics: `list[str]`, `dict[str, int]`, `tuple[int, str]`. Never `List`/`Dict`/`Tuple` from `typing`.
- `X | None` for optional (not `Optional[X]`); `X | Y` for unions (not `Union[X, Y]`).
- `typing.Protocol` for duck-typed interfaces (LLM providers, tracers, anything that should swap freely).
- `TypeAlias` (or `type` statement in 3.12+) for compound types used in more than one place.
- Avoid `Any`. Pick a narrower type, or use `object` when you genuinely accept anything.
- `from __future__ import annotations` is fine but not required; be consistent within a file.

**Example:**
```python
# Before
from typing import Optional, List, Dict, Tuple

def read_row(ctx, sheet: str, row: int,
             col_range: Optional[Tuple[int, int]] = None) -> List[Dict]:
    ...

# After
def read_row(ctx: WorkbookCtx, sheet: str, row: int,
             col_range: tuple[int, int] | None = None) -> list[Cell]:
    ...
```

**Checklist:**
- [ ] Every public function signature is fully annotated.
- [ ] No `Optional`, `List`, `Dict`, `Tuple`, `Union` imports from `typing`.
- [ ] No bare `Any` without a comment explaining why.
- [ ] `Protocol` is used where duck-typed swapping is intentional.
- [ ] Compound types used in 2+ places are aliased.

## 6. Error handling

Exceptions describe what went wrong with enough specificity that a caller can
decide what to do. Silent swallowing is a defect. Validation belongs at the
module boundary; inside, trust your types.

**Rules:**
- Raise specific exceptions (`ValueError`, `KeyError`, custom subclass) for actual errors. Bare `raise Exception(...)` is a defect.
- Return `None` only when "not found" is a legitimate result, and document that in the docstring.
- No bare `except:`. Always name the exception type.
- `except Exception:` is allowed only when (a) you log the exception and (b) you re-raise OR fall back to a documented default. Silent swallowing without either is a defect.
- Validate inputs at module boundaries (routers, public APIs, data load points). Inside a module, trust the types you declared.
- Custom exception classes inherit from the closest standard exception (`ValueError`, `RuntimeError`, `LookupError`) and live in the module that raises them.

**Example:**
```python
# Before — bare except, silent None, undocumented
def get_tracer(name: str = "tna_service"):
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except:
        return None

# After — narrow exception, documented stand-in
def get_tracer(name: str = "tna_service"):
    """Return an OTel tracer, or a no-op stand-in when OTel isn't installed."""
    try:
        from opentelemetry import trace
    except ImportError:
        return _NoopTracer()
    return trace.get_tracer(name)
```

**Checklist:**
- [ ] No bare `except:` in the file.
- [ ] Every `except Exception:` either re-raises or returns a documented fallback, and logs the cause.
- [ ] Returning `None` for "not found" is documented in the docstring.
- [ ] Custom exceptions inherit from a meaningful standard base.
- [ ] Input validation is at the boundary, not scattered through internals.

## 7. Imports

Imports are read first. Grouped, sorted, and absolute makes diffs clean.

**Rules:**
- Three groups, separated by a blank line: stdlib → third-party → local (`app.*`).
- Alphabetised within each group. (Ruff/isort will enforce this if configured.)
- Absolute imports only: `from app.models.extraction import PLI`, not `from .extraction import PLI`.
- Lazy imports inside function bodies are acceptable only when (a) the dependency is genuinely optional, or (b) to break a circular import. Add a one-line comment saying which.
- Never `from module import *`.

**Example:**
```python
# Before — mixed groups, relative import, wildcard
from .extraction import *
import os
from openpyxl.utils import column_index_from_string
from app.core.logs import get_logger

# After — three groups, alphabetised, absolute, explicit
import os

from openpyxl.utils import column_index_from_string

from app.core.logs import get_logger
from app.models.extraction import PLI, Stage
```

**Checklist:**
- [ ] Three import groups (stdlib, third-party, local) separated by blank lines.
- [ ] Each group alphabetised.
- [ ] No relative imports.
- [ ] No `import *`.
- [ ] Any lazy import inside a function carries a one-line reason comment.

## 8. Module organization

A file is a chapter: one responsibility, read top-to-bottom, split when it
picks up a second job.

**Rules:**
- One clear responsibility per file. If you'd write two distinct module docstrings, split.
- Public API at the top, private helpers below. Within a section, prefer narrative order: callers before callees where it doesn't force forward declarations.
- Soft size signal: a file approaching ~200 lines is a prompt to ask "is this still one concept?" — not a hard cap, but a checkpoint.
- `__init__.py` files re-export the package's public API. Put no logic in `__init__.py`.
- Avoid module-level mutable state. If config must persist, encapsulate it in a class or a `Settings` object.
- Constants and type aliases used across the module live at the top, after imports, before the first function.

**Example:**
```python
# Good shape — constants at top, public above private
_DATA_ROLES = {RowRole.ANCHOR, RowRole.CHILD}
_STRING_FIELDS = {"io_number", "style_code", ...}

def apply_plan(ctx, plan, name_map): ...    # public, top
def _coerce(field, val): ...                # private, below
def _read_with_merge(ws, row, col): ...     # private, below
```

**Checklist:**
- [ ] Module has a single clearly-named responsibility.
- [ ] Public API is above private helpers.
- [ ] Module-level constants and type aliases are at the top, after imports.
- [ ] `__init__.py` files contain no logic.
- [ ] No module-level mutable state outside encapsulated settings.

## 9. Test interaction

Production code must be testable without monkey-patching its internals. The
right seam is dependency injection, not a test-aware code path.

**Rules:**
- Accept dependencies through parameters or constructor injection. Don't reach for globals from inside a function.
- No mutation of global state at import time (no `os.environ[...] = ...` at module top, no DB connection on import, no side-effect logger reconfiguration).
- No `if TESTING:` branches or other test-only environment flags in production code.
- No test-only keyword arguments (`_fake_clock=None`). If you need a seam, make it a real, documented parameter.
- No imports from `tests/`; no reaching into test fixtures.

**Example:**
```python
# Before — production code with a test-only branch
def configure_tracing(service_name: str = "tna-service"):
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    # ... real setup ...

# After — production code with a clean DI seam; tests pass a fake endpoint
def configure_tracing(service_name: str = "tna-service",
                     otlp_endpoint: str | None = None):
    """Set up tracing. Returns None if OTel packages aren't available."""
    # ... real setup, ImportError handled cleanly ...
```

**Checklist:**
- [ ] No `if TESTING:` or `if PYTEST_CURRENT_TEST:` branches in production code.
- [ ] No test-only keyword arguments (leading-underscore "secret" params).
- [ ] No import-time global state mutation.
- [ ] Dependencies enter through parameters or constructors, not module globals.
- [ ] Production code does not import from `tests/`.

## 10. Self-review checklist

Run this against every file before commit. If any box is unchecked and there
is no `# allow-*` override with a reason, fix the file before committing.

**Naming (S1):**
- [ ] Function names are verb-first; class names are noun-first.
- [ ] Private helpers have a leading `_`; nothing public has one.
- [ ] No version suffixes (`_v2`), no `_helper`/`_util` filler.
- [ ] No single-letter names outside tight loops.
- [ ] Domain vocabulary matches the rest of the codebase.

**Functions (S2):**
- [ ] No body exceeds 40 lines, or carries `# allow-long: <reason>`.
- [ ] Each function does one nameable thing.
- [ ] Extracted helpers have concrete domain names, not structural ones.
- [ ] No hidden mutation where the name implies purity.

**Docstrings (S3):**
- [ ] Every public function, class, and module has a docstring.
- [ ] Private functions >10 lines or with non-obvious behaviour have one too.
- [ ] Summary line is ≤80 chars, imperative mood, ends in a period.
- [ ] No docstring restates the signature.

**Comments (S4):**
- [ ] No comment narrates what a well-named identifier already says.
- [ ] No plan-task names anywhere in the file.
- [ ] Surviving comments explain a constraint, workaround, or external reference.

**Types (S5):**
- [ ] Every public signature is fully annotated.
- [ ] Modern syntax: `list[X]`, `X | None`, `X | Y`. No `Optional/List/Dict/Tuple/Union` from `typing`.
- [ ] No bare `Any` without a comment.

**Errors (S6):**
- [ ] No bare `except:`.
- [ ] Every `except Exception:` logs the cause AND re-raises or falls back to a documented default.
- [ ] `None`-as-not-found is documented where used.

**Imports (S7):**
- [ ] Three groups (stdlib, third-party, local), blank line between, alphabetised within.
- [ ] No relative imports, no `import *`.
- [ ] Lazy imports carry a reason comment.

**Module (S8):**
- [ ] Single clear responsibility.
- [ ] Public API above private helpers.
- [ ] Constants at the top, after imports.
- [ ] No module-level mutable state outside a settings object.
- [ ] `__init__.py` is re-exports only.

**Tests (S9):**
- [ ] No `if TESTING:` branch and no test-only kwargs.
- [ ] No import-time side effects on global state.
- [ ] Dependencies enter through parameters or constructors.
- [ ] No imports from `tests/`.
