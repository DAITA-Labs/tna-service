# Migrate the Four Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move today's four LLM agents from `app/services/agents/` to `app/agents/<name>/` on the new substrate (Agent base class + lifecycle hooks). Each agent gains a real `validate_output` semantic gate.

**Architecture:** One folder per agent (`agent.py`, `schema.py`, `tuning.py`, `validators.py`, `tests/`). Prompts move to `app/prompts/<name>.py` as module-level string constants. Component wrappers in `app/components/<name>.py` make agents callable from the orchestrator. Migration order: SheetClassifier → LayoutHinter → PlanReviewer → FieldNamer (simplest first; PlanReviewer and FieldNamer carry the heaviest semantic validators).

**Tech Stack:** Python 3.12, Pydantic 2.6+, pydantic-settings, Haystack 2.10+, OpenTelemetry SDK 1.27+.

---

## Conventions

- Python 3.12+, modern types (`str | None`, `list[str]`, `dict[str, X]`).
- `from __future__ import annotations` at the top of every module.
- One-line imperative docstrings; ≤40-line functions; no narrative comments.
- Conventional commits (`feat/fix/chore/docs/test/refactor`) — one commit per task.
- TDD: write the failing test first, then the implementation that makes it pass.
- After every agent migration completes (its full section), `make test` AND `make eval-smoke` must be green before commit.
- Old `app/services/agents/<name>.py` and `app/prompts/workflow/<name>.md` are only deleted at the end of each agent's section, after the orchestrator is re-wired and tests pass.
- `app/models/artifacts.py` keeps a re-export shim (`from app.agents.<name>.schema import Foo`) until sub-plan 5 retires it.

---

## Section 1 — SheetClassifier migration

### 1.1 Scaffold the `app/agents/sheet_classifier/` folder

- [ ] Create `app/agents/sheet_classifier/__init__.py`:
  ```python
  """SheetClassifier agent — picks TNA-relevant sheets from a workbook."""
  from __future__ import annotations

  from app.agents.sheet_classifier.agent import SheetClassifierAgent
  from app.agents.sheet_classifier.schema import (
      SheetClassifierInputs,
      SheetClassifierOutput,
  )

  __all__ = ["SheetClassifierAgent", "SheetClassifierInputs", "SheetClassifierOutput"]
  ```
- [ ] Create empty `app/agents/sheet_classifier/tests/__init__.py`.
- [ ] Verify import surface: `python -c "from app.agents.sheet_classifier import SheetClassifierAgent"` raises `ImportError` (expected — modules not written yet).
- [ ] Commit `chore(agents): scaffold sheet_classifier folder`.

### 1.2 Move prompt to `app/prompts/sheet_classifier.py`

- [ ] Write the failing test `tests/unit/prompts/test_sheet_classifier_prompt.py`:
  ```python
  """Verify the SheetClassifier prompt string constant is importable + non-empty."""
  from __future__ import annotations

  from app.prompts import SHEET_CLASSIFIER


  def test_sheet_classifier_constant_loaded() -> None:
      """SHEET_CLASSIFIER is a non-empty module-level string."""
      assert isinstance(SHEET_CLASSIFIER, str)
      assert "SheetClassifier" in SHEET_CLASSIFIER
      assert "relevant_sheets" in SHEET_CLASSIFIER
  ```
- [ ] Run `pytest tests/unit/prompts/test_sheet_classifier_prompt.py -q` — expect ImportError.
- [ ] Create `app/prompts/sheet_classifier.py` (paste full content from `app/prompts/workflow/sheet_classifier.md`; substitute `{{SHARED}}` with `{SHARED}` for `.format()` at use site, or inline-import `SHARED` from `app/prompts/_shared.py` and concatenate):
  ```python
  """SheetClassifier prompt — picks TNA-relevant sheets from a workbook summary."""
  from __future__ import annotations

  from app.prompts._shared import SHARED

  SHEET_CLASSIFIER: str = f"""{SHARED}

  # SheetClassifier — role

  Given a workbook summary (sheet names, dimensions, file size), return the list
  of sheets that look like real TNA data and the list of sheets to skip.

  ## What counts as TNA-relevant

  - Has a tabular data band (header row + multiple data rows with PLI identity columns).
  - Or: looks like a per-PLI sheet (Orders Plan style — scattered Job No / Quantity /
    Delivery cells with stage bands underneath).

  ## What counts as noise (skip)

  - Tabs named "lAB", "log", "summary", "instructions", "info", "_sheet".
  - Tabs with only a handful of cells.
  - Tabs that duplicate another tab verbatim.

  ## Output

  Emit `relevant_sheets: list[str]` via the `emit_sheet_classifier` tool. If
  unsure, include the sheet — false positives are cheaper than false negatives.
  """
  ```
- [ ] If `app/prompts/_shared.py` does not yet exist (sub-plan 1 should have created it), create it now by loading `app/prompts/_shared.md` content into a `SHARED: str` constant.
- [ ] Update `app/prompts/__init__.py` to re-export: `from app.prompts.sheet_classifier import SHEET_CLASSIFIER`.
- [ ] Re-run the prompt test — expect green.
- [ ] Commit `refactor(prompts): move sheet_classifier prompt to python module`.

### 1.3 Move Pydantic schema to `app/agents/sheet_classifier/schema.py`

- [ ] Write failing test `tests/unit/agents/sheet_classifier/test_schema.py`:
  ```python
  """Verify SheetClassifier input + output schemas."""
  from __future__ import annotations

  from app.agents.sheet_classifier.schema import (
      SheetClassifierInputs,
      SheetClassifierOutput,
  )
  from app.models.artifacts import WorkbookSummary


  def test_output_defaults_empty() -> None:
      """SheetClassifierOutput defaults to empty list + None notes + None decision_notes."""
      out = SheetClassifierOutput()
      assert out.relevant_sheets == []
      assert out.notes is None
      assert out.decision_notes is None


  def test_inputs_carries_summary() -> None:
      """SheetClassifierInputs holds the WorkbookSummary."""
      summary = WorkbookSummary(sheet_count=1, file_size_kb=10, sheet_names=["A"])
      inputs = SheetClassifierInputs(workbook_summary=summary)
      assert inputs.workbook_summary.sheet_names == ["A"]
  ```
- [ ] Create `app/agents/sheet_classifier/schema.py`:
  ```python
  """SheetClassifier I/O schemas."""
  from __future__ import annotations

  from pydantic import BaseModel, ConfigDict, Field

  from app.models.artifacts import WorkbookSummary


  class SheetClassifierInputs(BaseModel):
      """Inputs to the SheetClassifier agent — wraps a WorkbookSummary."""

      model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)
      workbook_summary: WorkbookSummary


  class SheetClassifierOutput(BaseModel):
      """Structured output produced by the SheetClassifier agent."""

      model_config = ConfigDict(extra="ignore")
      relevant_sheets: list[str] = Field(default_factory=list)
      notes: str | None = None
      decision_notes: str | None = None
  ```
- [ ] Add re-export shim in `app/models/artifacts.py` (keep old import path working):
  ```python
  from app.agents.sheet_classifier.schema import SheetClassifierOutput  # noqa: F401
  ```
- [ ] Run `pytest tests/unit/agents/sheet_classifier/test_schema.py -q` — expect green.
- [ ] Commit `refactor(agents): move SheetClassifier schema to agent folder`.

### 1.4 Write `app/agents/sheet_classifier/tuning.py`

- [ ] Write failing test `tests/unit/agents/sheet_classifier/test_tuning.py`:
  ```python
  """Verify SheetClassifierTuning defaults."""
  from __future__ import annotations

  from app.agents.sheet_classifier.tuning import SheetClassifierTuning


  def test_defaults() -> None:
      """Defaults: max_retries=1, capture_decision_notes=False, confidence_gate=0.0."""
      t = SheetClassifierTuning()
      assert t.max_retries == 1
      assert t.capture_decision_notes is False
      assert t.confidence_gate == 0.0
      assert t.semantic_examples == []
      assert t.anti_pattern_examples == []
  ```
- [ ] Create `app/agents/sheet_classifier/tuning.py`:
  ```python
  """SheetClassifier tuning knobs."""
  from __future__ import annotations

  from pydantic import Field
  from pydantic_settings import BaseSettings, SettingsConfigDict


  class SheetClassifierTuning(BaseSettings):
      """Per-agent tuning for SheetClassifier."""

      model_config = SettingsConfigDict(env_prefix="TNA_SHEET_CLASSIFIER_", extra="ignore")
      max_retries: int = 1
      capture_decision_notes: bool = False
      confidence_gate: float = 0.0  # SheetClassifier has no confidence field
      semantic_examples: list[dict] = Field(default_factory=list)
      anti_pattern_examples: list[dict] = Field(default_factory=list)
  ```
- [ ] Run tuning test — expect green.
- [ ] Commit `refactor(agents): add SheetClassifier tuning module`.

### 1.5 Write `app/agents/sheet_classifier/validators.py`

- [ ] Write failing test `tests/unit/agents/sheet_classifier/test_validators.py`:
  ```python
  """Verify SheetClassifier validate_output semantic checks."""
  from __future__ import annotations

  from types import SimpleNamespace

  from app.agents._base import OutputVerdict
  from app.agents.sheet_classifier.schema import SheetClassifierOutput
  from app.agents.sheet_classifier.validators import validate_output


  def test_accepts_subset_of_workbook_sheets() -> None:
      """All returned sheets exist in the workbook → ok."""
      out = SheetClassifierOutput(relevant_sheets=["Sheet1", "Plan"])
      ctx = SimpleNamespace(sheet_names=["Sheet1", "Plan", "Notes"])
      verdict = validate_output(out, ctx)
      assert verdict.ok


  def test_rejects_unknown_sheet() -> None:
      """A relevant_sheets entry not in workbook → retry with reason."""
      out = SheetClassifierOutput(relevant_sheets=["Sheet1", "GHOST"])
      ctx = SimpleNamespace(sheet_names=["Sheet1", "Plan"])
      verdict = validate_output(out, ctx)
      assert not verdict.ok
      assert "GHOST" in verdict.reason


  def test_rejects_non_string_entries() -> None:
      """Non-string entry → retry."""
      out = SheetClassifierOutput.model_construct(relevant_sheets=[1, "Sheet1"])
      ctx = SimpleNamespace(sheet_names=["Sheet1"])
      verdict = validate_output(out, ctx)
      assert not verdict.ok
  ```
- [ ] Create `app/agents/sheet_classifier/validators.py`:
  ```python
  """SheetClassifier semantic validators."""
  from __future__ import annotations

  from typing import Any

  from app.agents._base import OutputVerdict
  from app.agents.sheet_classifier.schema import SheetClassifierInputs, SheetClassifierOutput


  def validate_input(inputs: SheetClassifierInputs, ctx: Any) -> OutputVerdict:
      """No-op input validation — summary shape already enforced by Pydantic."""
      return OutputVerdict.ok()


  def validate_output(output: SheetClassifierOutput, ctx: Any) -> OutputVerdict:
      """Reject entries that aren't strings or aren't sheet names in the workbook."""
      known = set(getattr(ctx, "sheet_names", []) or [])
      for entry in output.relevant_sheets:
          if not isinstance(entry, str):
              return OutputVerdict.retry(reason=f"relevant_sheets entry {entry!r} is not a string")
          if known and entry not in known:
              return OutputVerdict.retry(
                  reason=f"relevant_sheets entry {entry!r} is not a workbook sheet name",
              )
      return OutputVerdict.ok()
  ```
- [ ] Run validator tests — expect green.
- [ ] Commit `feat(agents): add SheetClassifier semantic validators`.

### 1.6 Write `app/agents/sheet_classifier/agent.py`

- [ ] Write failing test `tests/unit/agents/sheet_classifier/test_agent.py`:
  ```python
  """Verify SheetClassifierAgent wiring and build_input."""
  from __future__ import annotations

  from types import SimpleNamespace

  from app.agents.sheet_classifier.agent import SheetClassifierAgent
  from app.agents.sheet_classifier.schema import SheetClassifierInputs
  from app.models.artifacts import WorkbookSummary
  from tests.support.fake_llm import FakeLLM


  def test_build_input_emits_summary_lines() -> None:
      """build_input includes sheet_count, file_size_kb, and sheet_names."""
      agent = SheetClassifierAgent(llm=FakeLLM())
      summary = WorkbookSummary(sheet_count=3, file_size_kb=42, sheet_names=["A", "B", "C"])
      inputs = SheetClassifierInputs(workbook_summary=summary)
      ctx = SimpleNamespace(sheet_names=summary.sheet_names)
      text = agent.build_input(ctx, inputs)
      assert "3 sheets" in text
      assert "42 KB" in text
      assert "['A', 'B', 'C']" in text
  ```
- [ ] Create `app/agents/sheet_classifier/agent.py`:
  ```python
  """SheetClassifier Agent — picks TNA-relevant sheets from a workbook summary."""
  from __future__ import annotations

  from typing import Any

  from app.agents._base import Agent
  from app.agents.sheet_classifier.schema import SheetClassifierInputs, SheetClassifierOutput
  from app.agents.sheet_classifier.tuning import SheetClassifierTuning
  from app.agents.sheet_classifier.validators import validate_input, validate_output
  from app.prompts import SHEET_CLASSIFIER


  class SheetClassifierAgent(Agent[SheetClassifierInputs, SheetClassifierOutput]):
      """Single-call LLM agent: WorkbookSummary → list of relevant sheet names."""

      name = "sheet_classifier"
      prompt = SHEET_CLASSIFIER
      output_schema = SheetClassifierOutput
      tuning_cls = SheetClassifierTuning
      validate_input = staticmethod(validate_input)
      validate_output = staticmethod(validate_output)

      def build_input(self, ctx: Any, inputs: SheetClassifierInputs) -> str:
          """Render the WorkbookSummary into the user prompt body."""
          s = inputs.workbook_summary
          return "\n".join([
              f"# Workbook: {s.sheet_count} sheets, {s.file_size_kb} KB",
              f"sheet_names: {s.sheet_names}",
              "",
              "Classify each sheet as TNA-relevant or noise.",
          ])
  ```
- [ ] Run agent test — expect green.
- [ ] Commit `feat(agents): add SheetClassifierAgent on new substrate`.

### 1.7 Add `Component` wrapper at `app/components/sheet_classifier.py`

- [ ] Write failing test `tests/unit/components/test_sheet_classifier_component.py`:
  ```python
  """Verify SheetClassifier component wraps the agent + falls back on failure."""
  from __future__ import annotations

  from types import SimpleNamespace

  from app.components.sheet_classifier import SheetClassifier
  from app.models.artifacts import WorkbookSummary
  from tests.support.fake_llm import FakeLLM


  def test_component_returns_agent_output() -> None:
      """Happy path: agent succeeds → relevant_sheets propagated."""
      llm = FakeLLM(response={"relevant_sheets": ["A"]})
      comp = SheetClassifier(llm=llm)
      summary = WorkbookSummary(sheet_count=2, file_size_kb=10, sheet_names=["A", "B"])
      ctx = SimpleNamespace(sheet_names=summary.sheet_names)
      out = comp.run(workbook_ctx=ctx, workbook_summary=summary)
      assert out["relevant_sheets"] == ["A"]


  def test_component_falls_back_on_failure() -> None:
      """Agent failure → fallback to all sheet names."""
      llm = FakeLLM(force_failure=True)
      comp = SheetClassifier(llm=llm)
      summary = WorkbookSummary(sheet_count=2, file_size_kb=10, sheet_names=["A", "B"])
      ctx = SimpleNamespace(sheet_names=summary.sheet_names)
      out = comp.run(workbook_ctx=ctx, workbook_summary=summary)
      assert out["relevant_sheets"] == ["A", "B"]
  ```
- [ ] Create `app/components/sheet_classifier.py`:
  ```python
  """SheetClassifier Haystack component — wraps SheetClassifierAgent."""
  from __future__ import annotations

  from typing import Any

  from haystack import component

  from app.agents._base import AgentRunFailure
  from app.agents.sheet_classifier import SheetClassifierAgent
  from app.agents.sheet_classifier.schema import SheetClassifierInputs
  from app.core.logs import get_logger
  from app.inferencing._base import Provider

  log = get_logger(__name__)


  @component
  class SheetClassifier:
      """Pipeline component that emits `relevant_sheets` for one workbook."""

      def __init__(self, llm: Provider) -> None:
          """Construct the wrapped agent with the LLM provider."""
          self.agent = SheetClassifierAgent(llm=llm)

      @component.output_types(relevant_sheets=list)
      def run(self, workbook_ctx: Any, workbook_summary: Any) -> dict:
          """Run the agent and fall back to all sheet names on failure."""
          ctx = _ctx_with_sheet_names(workbook_ctx, workbook_summary)
          result = self.agent.run(ctx, SheetClassifierInputs(workbook_summary=workbook_summary))
          if isinstance(result, AgentRunFailure):
              log.warning("agent_fallback_used", agent="sheet_classifier")
              return {"relevant_sheets": list(workbook_summary.sheet_names)}
          return {"relevant_sheets": result.relevant_sheets}


  def _ctx_with_sheet_names(workbook_ctx: Any, summary: Any) -> Any:
      """Attach sheet_names to ctx so validate_output can see them."""
      if hasattr(workbook_ctx, "sheet_names"):
          return workbook_ctx
      setattr(workbook_ctx, "sheet_names", list(summary.sheet_names))
      return workbook_ctx
  ```
- [ ] Run component test — expect green.
- [ ] Commit `feat(components): add SheetClassifier component wrapper`.

### 1.8 Add gate-behavior tests with FakeLLM.script_responses

- [ ] Add to `tests/unit/agents/sheet_classifier/test_agent.py`:
  ```python
  def test_retries_when_validate_output_rejects(monkeypatch) -> None:
      """First response has unknown sheet → retry; second response passes."""
      bad = {"relevant_sheets": ["GHOST"]}
      good = {"relevant_sheets": ["A"]}
      llm = FakeLLM.script_responses(bad, good)
      agent = SheetClassifierAgent(llm=llm)
      summary = WorkbookSummary(sheet_count=1, file_size_kb=10, sheet_names=["A"])
      ctx = SimpleNamespace(sheet_names=summary.sheet_names)
      result = agent.run(ctx, SheetClassifierInputs(workbook_summary=summary))
      assert result.relevant_sheets == ["A"]
      assert llm.call_count == 2


  def test_failure_after_retry_exhausted() -> None:
      """Both responses semantic-fail → AgentRunFailure."""
      bad1 = {"relevant_sheets": ["GHOST"]}
      bad2 = {"relevant_sheets": ["GHOST2"]}
      llm = FakeLLM.script_responses(bad1, bad2)
      agent = SheetClassifierAgent(llm=llm)
      summary = WorkbookSummary(sheet_count=1, file_size_kb=10, sheet_names=["A"])
      ctx = SimpleNamespace(sheet_names=summary.sheet_names)
      result = agent.run(ctx, SheetClassifierInputs(workbook_summary=summary))
      from app.agents._base import AgentRunFailure
      assert isinstance(result, AgentRunFailure)
  ```
- [ ] Run agent tests — expect green.
- [ ] Commit `test(agents): cover SheetClassifier semantic gate retries`.

### 1.9 Update orchestrator `app/services/extraction.py` to import new component

- [ ] Edit `app/services/extraction.py` lines 47–50:
  ```python
  from app.components.sheet_classifier import SheetClassifier  # was: app.services.agents.sheet_classifier
  ```
  Keep other agent imports unchanged for now.
- [ ] Run `pytest tests -q -m "not live"` — expect green.
- [ ] Commit `refactor(extraction): wire new SheetClassifier component`.

### 1.10 Delete old SheetClassifier code

- [ ] Delete `app/services/agents/sheet_classifier.py`.
- [ ] Delete `app/prompts/workflow/sheet_classifier.md`.
- [ ] Move old test file (if any) `tests/unit/agents/test_sheet_classifier*.py` into `tests/unit/agents/sheet_classifier/` (already done by step 1.6/1.8); confirm no orphaned test file references the old module.
- [ ] Grep for residual imports: `rg "from app.services.agents.sheet_classifier|app/prompts/workflow/sheet_classifier" .` — expect zero results.
- [ ] Run `make test` — expect green.
- [ ] Commit `chore(agents): delete old sheet_classifier service module`.

### 1.11 Checkpoint — `make eval-smoke`

- [ ] Run `make eval-smoke`. Expected output: smoke matrix matches the baseline captured before the migration started (no regressions on the smoke subset).
- [ ] If a row regresses, halt and investigate before continuing to Section 2.
- [ ] Commit `chore(eval): confirm eval-smoke green after sheet_classifier migration` (empty commit with `--allow-empty` if no file changes).

---

## Section 2 — LayoutHinter migration

### 2.1 Scaffold the `app/agents/layout_hinter/` folder

- [ ] Create `app/agents/layout_hinter/__init__.py`:
  ```python
  """LayoutHinter agent — disambiguates identity_column and pli_mode signals."""
  from __future__ import annotations

  from app.agents.layout_hinter.agent import LayoutHinterAgent
  from app.agents.layout_hinter.schema import LayoutHinterInputs, LayoutHints

  __all__ = ["LayoutHinterAgent", "LayoutHinterInputs", "LayoutHints"]
  ```
- [ ] Create `app/agents/layout_hinter/tests/__init__.py`.
- [ ] Commit `chore(agents): scaffold layout_hinter folder`.

### 2.2 Move prompt to `app/prompts/layout_hinter.py`

- [ ] Write failing test `tests/unit/prompts/test_layout_hinter_prompt.py`:
  ```python
  """Verify LayoutHinter prompt loads + contains expected sentinels."""
  from __future__ import annotations

  from app.prompts import LAYOUT_HINTER


  def test_layout_hinter_constant_loaded() -> None:
      """LAYOUT_HINTER is non-empty + mentions identity_column + pli_mode."""
      assert isinstance(LAYOUT_HINTER, str)
      assert "LayoutHinter" in LAYOUT_HINTER
      assert "identity_column" in LAYOUT_HINTER
      assert "pli_mode" in LAYOUT_HINTER
  ```
- [ ] Run prompt test — expect ImportError.
- [ ] Create `app/prompts/layout_hinter.py`:
  ```python
  """LayoutHinter prompt — disambiguates identity_column and pli_mode."""
  from __future__ import annotations

  from app.prompts._shared import SHARED

  LAYOUT_HINTER: str = f"""You are LayoutHinter. The deterministic SheetRowPlanner could not decide one
  or more of the following:
  - which column is the identity column (when there are 2+ candidates)
  - which pli_mode is correct for this sheet

  You are given the sheet's signals + a top-left peek. Pick the best
  identity_column and/or pli_mode. Return JSON matching the LayoutHints schema.

  Rules:
  - Prefer columns whose header text contains "IO", "JOB", "BUYER PO".
  - Prefer pli_mode=SHEET_IS_PLI only when the sheet has no row-tabular data.
  - Keep notes short; one sentence per signal you used.

  {SHARED}
  """
  ```
- [ ] Update `app/prompts/__init__.py` to add `from app.prompts.layout_hinter import LAYOUT_HINTER`.
- [ ] Re-run prompt test — expect green.
- [ ] Commit `refactor(prompts): move layout_hinter prompt to python module`.

### 2.3 Move Pydantic schema to `app/agents/layout_hinter/schema.py`

- [ ] Write failing test `tests/unit/agents/layout_hinter/test_schema.py`:
  ```python
  """Verify LayoutHinter input + output schemas."""
  from __future__ import annotations

  from app.agents.layout_hinter.schema import LayoutHinterInputs, LayoutHints
  from app.models.artifacts import SheetSignals


  def test_layouthints_defaults() -> None:
      """LayoutHints defaults to None identity + mode + empty notes + None decision_notes."""
      h = LayoutHints()
      assert h.identity_column_suggestion is None
      assert h.mode_suggestion is None
      assert h.notes == []
      assert h.decision_notes is None


  def test_inputs_carries_signals_and_sheet() -> None:
      """LayoutHinterInputs wraps SheetSignals + sheet name."""
      sig = SheetSignals()
      inputs = LayoutHinterInputs(sheet="Plan", signals=sig)
      assert inputs.sheet == "Plan"
  ```
- [ ] Create `app/agents/layout_hinter/schema.py`:
  ```python
  """LayoutHinter I/O schemas."""
  from __future__ import annotations

  from pydantic import BaseModel, ConfigDict, Field

  from app.models.artifacts import SheetSignals


  class LayoutHinterInputs(BaseModel):
      """Inputs to the LayoutHinter agent — sheet name + signals."""

      model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)
      sheet: str
      signals: SheetSignals


  class LayoutHints(BaseModel):
      """LayoutHinter's output — disambiguation hints for the planner."""

      model_config = ConfigDict(extra="ignore")
      identity_column_suggestion: str | None = None
      mode_suggestion: str | None = None
      notes: list[str] = Field(default_factory=list)
      decision_notes: str | None = None
  ```
- [ ] Add re-export shim in `app/models/artifacts.py`: `from app.agents.layout_hinter.schema import LayoutHints  # noqa: F401`.
- [ ] Delete the original `class LayoutHints` definition from `app/models/artifacts.py`.
- [ ] Run schema test — expect green.
- [ ] Commit `refactor(agents): move LayoutHints schema to agent folder`.

### 2.4 Write `app/agents/layout_hinter/tuning.py`

- [ ] Write failing test `tests/unit/agents/layout_hinter/test_tuning.py`:
  ```python
  """Verify LayoutHinterTuning defaults."""
  from __future__ import annotations

  from app.agents.layout_hinter.tuning import LayoutHinterTuning


  def test_defaults() -> None:
      """Defaults: max_retries=1, capture_decision_notes=False, confidence_gate=0.0."""
      t = LayoutHinterTuning()
      assert t.max_retries == 1
      assert t.capture_decision_notes is False
      assert t.confidence_gate == 0.0
      assert t.semantic_examples == []
      assert t.anti_pattern_examples == []
  ```
- [ ] Create `app/agents/layout_hinter/tuning.py`:
  ```python
  """LayoutHinter tuning knobs."""
  from __future__ import annotations

  from pydantic import Field
  from pydantic_settings import BaseSettings, SettingsConfigDict


  class LayoutHinterTuning(BaseSettings):
      """Per-agent tuning for LayoutHinter."""

      model_config = SettingsConfigDict(env_prefix="TNA_LAYOUT_HINTER_", extra="ignore")
      max_retries: int = 1
      capture_decision_notes: bool = False
      confidence_gate: float = 0.0  # LayoutHinter has no confidence field
      semantic_examples: list[dict] = Field(default_factory=list)
      anti_pattern_examples: list[dict] = Field(default_factory=list)
  ```
- [ ] Run tuning test — expect green.
- [ ] Commit `refactor(agents): add LayoutHinter tuning module`.

### 2.5 Write `app/agents/layout_hinter/validators.py`

- [ ] Write failing test `tests/unit/agents/layout_hinter/test_validators.py`:
  ```python
  """Verify LayoutHinter validate_output semantic checks."""
  from __future__ import annotations

  from types import SimpleNamespace

  from app.agents.layout_hinter.schema import LayoutHints
  from app.agents.layout_hinter.validators import validate_output


  def test_accepts_valid_column_letter() -> None:
      """identity_column_suggestion='AA' → ok."""
      out = LayoutHints(identity_column_suggestion="AA", mode_suggestion="row_per_pli")
      verdict = validate_output(out, SimpleNamespace())
      assert verdict.ok


  def test_rejects_lowercase_column() -> None:
      """identity_column_suggestion='a' → retry."""
      out = LayoutHints(identity_column_suggestion="a")
      verdict = validate_output(out, SimpleNamespace())
      assert not verdict.ok
      assert "column letter" in verdict.reason


  def test_rejects_numeric_column() -> None:
      """identity_column_suggestion='1' → retry."""
      out = LayoutHints(identity_column_suggestion="1")
      verdict = validate_output(out, SimpleNamespace())
      assert not verdict.ok


  def test_rejects_unknown_mode() -> None:
      """mode_suggestion='weird' → retry."""
      out = LayoutHints(mode_suggestion="weird")
      verdict = validate_output(out, SimpleNamespace())
      assert not verdict.ok
      assert "pli_mode" in verdict.reason


  def test_accepts_all_three_modes() -> None:
      """Each of the 3 PliMode values is accepted."""
      for mode in ("row_per_pli", "sheet_is_pli", "section_per_pli"):
          out = LayoutHints(mode_suggestion=mode)
          assert validate_output(out, SimpleNamespace()).ok


  def test_accepts_none_fields() -> None:
      """Both fields None → ok."""
      assert validate_output(LayoutHints(), SimpleNamespace()).ok
  ```
- [ ] Create `app/agents/layout_hinter/validators.py`:
  ```python
  """LayoutHinter semantic validators."""
  from __future__ import annotations

  import re
  from typing import Any

  from app.agents._base import OutputVerdict
  from app.agents.layout_hinter.schema import LayoutHinterInputs, LayoutHints
  from app.enums.pli_mode import PliMode

  _COL_RE = re.compile(r"^[A-Z]+$")
  _VALID_MODES = {m.value for m in PliMode}


  def validate_input(inputs: LayoutHinterInputs, ctx: Any) -> OutputVerdict:
      """No-op input validation — Pydantic handles shape."""
      return OutputVerdict.ok()


  def validate_output(output: LayoutHints, ctx: Any) -> OutputVerdict:
      """Reject non-column-letter identity hints and unknown pli_mode values."""
      col = output.identity_column_suggestion
      if col is not None and not _COL_RE.match(col):
          return OutputVerdict.retry(
              reason=f"identity_column_suggestion {col!r} is not a valid Excel column letter",
          )
      mode = output.mode_suggestion
      if mode is not None and mode not in _VALID_MODES:
          return OutputVerdict.retry(
              reason=f"mode_suggestion {mode!r} is not a valid pli_mode "
                     f"(expected one of {sorted(_VALID_MODES)})",
          )
      return OutputVerdict.ok()
  ```
- [ ] Run validator tests — expect green.
- [ ] Commit `feat(agents): add LayoutHinter semantic validators`.

### 2.6 Write `app/agents/layout_hinter/agent.py`

- [ ] Write failing test `tests/unit/agents/layout_hinter/test_agent.py`:
  ```python
  """Verify LayoutHinterAgent wiring and build_input."""
  from __future__ import annotations

  from types import SimpleNamespace

  from app.agents.layout_hinter.agent import LayoutHinterAgent
  from app.agents.layout_hinter.schema import LayoutHinterInputs
  from app.models.artifacts import SheetSignals
  from tests.support.fake_llm import FakeLLM


  def test_build_input_includes_signals_and_peek(monkeypatch) -> None:
      """build_input renders sheet name, signals dump, and peek_sheet grid."""
      from app.repositories.workbook_tools._registry import TOOL_REGISTRY
      grid = SimpleNamespace(cells=[
          SimpleNamespace(address="A1", dtype="str", value="HEADER"),
      ])
      monkeypatch.setitem(TOOL_REGISTRY, "peek_sheet", lambda ctx, sheet, rows, cols: grid)
      agent = LayoutHinterAgent(llm=FakeLLM())
      inputs = LayoutHinterInputs(sheet="Plan", signals=SheetSignals())
      text = agent.build_input(SimpleNamespace(), inputs)
      assert "# Sheet: Plan" in text
      assert "## Signals:" in text
      assert "A1 [str]: 'HEADER'" in text
  ```
- [ ] Create `app/agents/layout_hinter/agent.py`:
  ```python
  """LayoutHinter Agent — disambiguates identity_column + pli_mode."""
  from __future__ import annotations

  from typing import Any

  from app.agents._base import Agent
  from app.agents.layout_hinter.schema import LayoutHinterInputs, LayoutHints
  from app.agents.layout_hinter.tuning import LayoutHinterTuning
  from app.agents.layout_hinter.validators import validate_input, validate_output
  from app.prompts import LAYOUT_HINTER
  from app.repositories.workbook_tools._registry import TOOL_REGISTRY


  class LayoutHinterAgent(Agent[LayoutHinterInputs, LayoutHints]):
      """Single-call LLM agent: signals + peek → LayoutHints."""

      name = "layout_hinter"
      prompt = LAYOUT_HINTER
      output_schema = LayoutHints
      tuning_cls = LayoutHinterTuning
      validate_input = staticmethod(validate_input)
      validate_output = staticmethod(validate_output)

      def build_input(self, ctx: Any, inputs: LayoutHinterInputs) -> str:
          """Render sheet name, signals model_dump, and a top-left 10x15 grid peek."""
          peek = TOOL_REGISTRY.get("peek_sheet")
          grid = peek(ctx, inputs.sheet, rows=10, cols=15)
          lines = [
              f"# Sheet: {inputs.sheet}",
              "## Signals:",
              str(inputs.signals.model_dump()),
              "",
              "## Top-left peek (rows 1..10, cols 1..15):",
          ]
          for c in grid.cells:
              lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
          return "\n".join(lines)
  ```
- [ ] Run agent test — expect green.
- [ ] Commit `feat(agents): add LayoutHinterAgent on new substrate`.

### 2.7 Add `Component` wrapper at `app/components/layout_hinter.py`

- [ ] Write failing test `tests/unit/components/test_layout_hinter_component.py`:
  ```python
  """Verify LayoutHinter component fallback + happy path."""
  from __future__ import annotations

  from types import SimpleNamespace

  from app.agents.layout_hinter.schema import LayoutHints
  from app.components.layout_hinter import LayoutHinter
  from app.models.artifacts import SheetSignals
  from tests.support.fake_llm import FakeLLM


  def test_happy_path(monkeypatch) -> None:
      """Agent returns hints → component forwards them."""
      from app.repositories.workbook_tools._registry import TOOL_REGISTRY
      monkeypatch.setitem(TOOL_REGISTRY, "peek_sheet",
                          lambda ctx, sheet, rows, cols: SimpleNamespace(cells=[]))
      llm = FakeLLM(response={"identity_column_suggestion": "B"})
      comp = LayoutHinter(llm=llm)
      out = comp.run(workbook_ctx=SimpleNamespace(), sheet="P", signals=SheetSignals())
      assert isinstance(out["hints"], LayoutHints)
      assert out["hints"].identity_column_suggestion == "B"


  def test_fallback_on_failure(monkeypatch) -> None:
      """Agent failure → empty LayoutHints."""
      from app.repositories.workbook_tools._registry import TOOL_REGISTRY
      monkeypatch.setitem(TOOL_REGISTRY, "peek_sheet",
                          lambda ctx, sheet, rows, cols: SimpleNamespace(cells=[]))
      llm = FakeLLM(force_failure=True)
      comp = LayoutHinter(llm=llm)
      out = comp.run(workbook_ctx=SimpleNamespace(), sheet="P", signals=SheetSignals())
      assert out["hints"].identity_column_suggestion is None
  ```
- [ ] Create `app/components/layout_hinter.py`:
  ```python
  """LayoutHinter Haystack component — wraps LayoutHinterAgent."""
  from __future__ import annotations

  from typing import Any

  from haystack import component

  from app.agents._base import AgentRunFailure
  from app.agents.layout_hinter import LayoutHinterAgent
  from app.agents.layout_hinter.schema import LayoutHinterInputs, LayoutHints
  from app.core.logs import get_logger
  from app.inferencing._base import Provider
  from app.models.artifacts import SheetSignals

  log = get_logger(__name__)


  @component
  class LayoutHinter:
      """Pipeline component that resolves layout ambiguity for one sheet."""

      def __init__(self, llm: Provider) -> None:
          """Construct the wrapped agent with the LLM provider."""
          self.agent = LayoutHinterAgent(llm=llm)

      @component.output_types(hints=LayoutHints)
      def run(self, workbook_ctx: Any, sheet: str, signals: SheetSignals) -> dict:
          """Run the agent; fall back to empty LayoutHints on failure."""
          inputs = LayoutHinterInputs(sheet=sheet, signals=signals)
          result = self.agent.run(workbook_ctx, inputs)
          if isinstance(result, AgentRunFailure):
              log.warning("agent_fallback_used", agent="layout_hinter")
              return {"hints": LayoutHints()}
          return {"hints": result}
  ```
- [ ] Run component test — expect green.
- [ ] Commit `feat(components): add LayoutHinter component wrapper`.

### 2.8 Add gate-behavior tests

- [ ] Append to `tests/unit/agents/layout_hinter/test_agent.py`:
  ```python
  def test_retries_on_invalid_column(monkeypatch) -> None:
      """First response has bad column letter → retry; second passes."""
      from app.repositories.workbook_tools._registry import TOOL_REGISTRY
      monkeypatch.setitem(TOOL_REGISTRY, "peek_sheet",
                          lambda ctx, sheet, rows, cols: SimpleNamespace(cells=[]))
      bad = {"identity_column_suggestion": "ab"}
      good = {"identity_column_suggestion": "AB"}
      llm = FakeLLM.script_responses(bad, good)
      agent = LayoutHinterAgent(llm=llm)
      result = agent.run(
          SimpleNamespace(),
          LayoutHinterInputs(sheet="P", signals=SheetSignals()),
      )
      assert result.identity_column_suggestion == "AB"
      assert llm.call_count == 2
  ```
- [ ] Run agent tests — expect green.
- [ ] Commit `test(agents): cover LayoutHinter semantic gate retry`.

### 2.9 Update orchestrator import

- [ ] Edit `app/services/extraction.py`: change `from app.services.agents.layout_hinter import LayoutHinter` → `from app.components.layout_hinter import LayoutHinter`.
- [ ] Run `make test` — expect green.
- [ ] Commit `refactor(extraction): wire new LayoutHinter component`.

### 2.10 Delete old LayoutHinter code

- [ ] Delete `app/services/agents/layout_hinter.py`.
- [ ] Delete `app/prompts/workflow/layout_hinter.md`.
- [ ] Grep `rg "from app.services.agents.layout_hinter|app/prompts/workflow/layout_hinter" .` — expect zero results.
- [ ] Run `make test` — expect green.
- [ ] Commit `chore(agents): delete old layout_hinter service module`.

### 2.11 Checkpoint — `make eval-smoke`

- [ ] Run `make eval-smoke`. Expected: no regression vs baseline.
- [ ] If regression, halt and investigate.
- [ ] Commit `chore(eval): confirm eval-smoke green after layout_hinter migration` (allow-empty).

---

## Section 3 — PlanReviewer migration

### 3.1 Scaffold the `app/agents/plan_reviewer/` folder

- [ ] Create `app/agents/plan_reviewer/__init__.py`:
  ```python
  """PlanReviewer agent — judges SheetPlan correctness, returns row corrections."""
  from __future__ import annotations

  from app.agents.plan_reviewer.agent import PlanReviewerAgent
  from app.agents.plan_reviewer.schema import (
      PlanReviewerInputs,
      PlanVerdict,
      RowCorrection,
  )

  __all__ = ["PlanReviewerAgent", "PlanReviewerInputs", "PlanVerdict", "RowCorrection"]
  ```
- [ ] Create `app/agents/plan_reviewer/tests/__init__.py`.
- [ ] Commit `chore(agents): scaffold plan_reviewer folder`.

### 3.2 Move prompt to `app/prompts/plan_reviewer.py`

- [ ] Write failing test `tests/unit/prompts/test_plan_reviewer_prompt.py`:
  ```python
  """Verify PlanReviewer prompt loads + contains sentinels."""
  from __future__ import annotations

  from app.prompts import PLAN_REVIEWER


  def test_plan_reviewer_constant_loaded() -> None:
      """PLAN_REVIEWER mentions PlanReviewer + row_corrections + ≤5 limit."""
      assert isinstance(PLAN_REVIEWER, str)
      assert "PlanReviewer" in PLAN_REVIEWER
      assert "row_corrections" in PLAN_REVIEWER
      assert "≤5" in PLAN_REVIEWER
  ```
- [ ] Create `app/prompts/plan_reviewer.py`:
  ```python
  """PlanReviewer prompt — judges SheetPlan correctness."""
  from __future__ import annotations

  from app.prompts._shared import SHARED

  PLAN_REVIEWER: str = f"""You are PlanReviewer. You are given a draft SheetPlan + Tier 1/2 validator
  findings + a peek at the sheet. Your job is to judge whether the plan looks
  correct.

  Output JSON matching PlanVerdict:
  - verdict: "looks_correct" or "needs_fix"
  - row_corrections: list of {{row, current_role, suggested_role, anchor_idx?, reason}}
  - identity_column_suggestion: column letter or null
  - warnings: short strings flagging stage-band / KV anchor concerns
  - confidence: 0..1

  Rules:
  - If you disagree with a strong deterministic signal (e.g., sum-of-children
    matches a TOTAL row), say so in warnings but DO NOT override — the det
    classification will win.
  - Be specific about row numbers. Do not hallucinate row indices outside the
    plan you are shown.
  - Limit row_corrections to ≤5 items.

  {SHARED}
  """
  ```
- [ ] Update `app/prompts/__init__.py` with `from app.prompts.plan_reviewer import PLAN_REVIEWER`.
- [ ] Run prompt test — expect green.
- [ ] Commit `refactor(prompts): move plan_reviewer prompt to python module`.

### 3.3 Move Pydantic schema to `app/agents/plan_reviewer/schema.py`

- [ ] Write failing test `tests/unit/agents/plan_reviewer/test_schema.py`:
  ```python
  """Verify PlanReviewer input + output schemas."""
  from __future__ import annotations

  from app.agents.plan_reviewer.schema import PlanReviewerInputs, PlanVerdict, RowCorrection
  from app.models.artifacts import SheetPlan


  def test_verdict_defaults() -> None:
      """PlanVerdict defaults to looks_correct + empty list fields + None decision_notes."""
      v = PlanVerdict()
      assert v.verdict == "looks_correct"
      assert v.row_corrections == []
      assert v.identity_column_suggestion is None
      assert v.warnings == []
      assert v.confidence == 1.0
      assert v.decision_notes is None


  def test_row_correction_parses_string_role() -> None:
      """RowCorrection accepts suggested_role as a string."""
      rc = RowCorrection(row=5, current_role="header", suggested_role="anchor",
                         reason="data row")
      assert rc.row == 5
      assert rc.suggested_role == "anchor"
  ```
- [ ] Create `app/agents/plan_reviewer/schema.py`:
  ```python
  """PlanReviewer I/O schemas — strongly typed RowCorrection replaces dict[str, Any]."""
  from __future__ import annotations

  from typing import Any

  from pydantic import BaseModel, ConfigDict, Field

  from app.models.artifacts import SheetPlan, ValidationFinding


  class RowCorrection(BaseModel):
      """One correction the PlanReviewer wants applied to a SheetPlan row."""

      model_config = ConfigDict(extra="ignore")
      row: int
      current_role: str | None = None
      suggested_role: str
      anchor_idx: int | None = None
      reason: str | None = None


  class PlanReviewerInputs(BaseModel):
      """Inputs to PlanReviewer — SheetPlan + tier-1/2 findings."""

      model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)
      plan: SheetPlan
      findings: list[ValidationFinding] = Field(default_factory=list)


  class PlanVerdict(BaseModel):
      """PlanReviewer's output — verdict + optional row corrections."""

      model_config = ConfigDict(extra="ignore")
      verdict: str = "looks_correct"
      row_corrections: list[RowCorrection] = Field(default_factory=list)
      identity_column_suggestion: str | None = None
      warnings: list[str] = Field(default_factory=list)
      confidence: float = 1.0
      decision_notes: str | None = None
  ```
- [ ] In `app/models/artifacts.py`: delete the original `class PlanVerdict` definition; add re-export shim `from app.agents.plan_reviewer.schema import PlanVerdict, RowCorrection  # noqa: F401`.
- [ ] Run schema tests — expect green.
- [ ] Commit `refactor(agents): move PlanVerdict schema to agent folder`.

### 3.4 Write `app/agents/plan_reviewer/tuning.py`

- [ ] Write failing test `tests/unit/agents/plan_reviewer/test_tuning.py`:
  ```python
  """Verify PlanReviewerTuning defaults."""
  from __future__ import annotations

  from app.agents.plan_reviewer.tuning import PlanReviewerTuning


  def test_defaults() -> None:
      """Defaults: max_retries=1, confidence_gate=0.85 (from old _CONFIDENCE_GATE)."""
      t = PlanReviewerTuning()
      assert t.max_retries == 1
      assert t.capture_decision_notes is False
      assert t.confidence_gate == 0.85
      assert t.max_row_corrections == 5
  ```
- [ ] Create `app/agents/plan_reviewer/tuning.py`:
  ```python
  """PlanReviewer tuning knobs."""
  from __future__ import annotations

  from pydantic import Field
  from pydantic_settings import BaseSettings, SettingsConfigDict


  class PlanReviewerTuning(BaseSettings):
      """Per-agent tuning for PlanReviewer."""

      model_config = SettingsConfigDict(env_prefix="TNA_PLAN_REVIEWER_", extra="ignore")
      max_retries: int = 1
      capture_decision_notes: bool = False
      confidence_gate: float = 0.85  # from old _CONFIDENCE_GATE in extraction.py
      max_row_corrections: int = 5
      semantic_examples: list[dict] = Field(default_factory=list)
      anti_pattern_examples: list[dict] = Field(default_factory=list)
  ```
- [ ] Run tuning test — expect green.
- [ ] Commit `refactor(agents): add PlanReviewer tuning module`.

### 3.5 Write `app/agents/plan_reviewer/validators.py` — the load-bearing gate

- [ ] Write failing test `tests/unit/agents/plan_reviewer/test_validators.py`:
  ```python
  """Verify PlanReviewer load-bearing validate_output gates."""
  from __future__ import annotations

  from types import SimpleNamespace

  from app.agents.plan_reviewer.schema import PlanVerdict, RowCorrection
  from app.agents.plan_reviewer.validators import validate_output
  from app.enums.row_role import RowRole
  from app.models.artifacts import RowSpec


  def _plan_with_rows(*idxs: int) -> SimpleNamespace:
      """Build a stub ctx exposing a list of RowSpecs by their idx values."""
      rows = [RowSpec(idx=i, role=RowRole.DATA) for i in idxs]
      return SimpleNamespace(plan=SimpleNamespace(rows=rows))


  def test_accepts_valid_corrections() -> None:
      """All corrections reference existing rows + valid roles + confidence in [0,1]."""
      out = PlanVerdict(
          verdict="needs_fix",
          row_corrections=[RowCorrection(row=3, suggested_role="anchor")],
          confidence=0.7,
      )
      verdict = validate_output(out, _plan_with_rows(1, 2, 3, 4))
      assert verdict.ok


  def test_rejects_nonexistent_row() -> None:
      """row_corrections[].row not in plan.rows.idx → retry."""
      out = PlanVerdict(
          verdict="needs_fix",
          row_corrections=[RowCorrection(row=99, suggested_role="anchor")],
      )
      verdict = validate_output(out, _plan_with_rows(1, 2, 3))
      assert not verdict.ok
      assert "99" in verdict.reason
      assert "non-existent" in verdict.reason


  def test_rejects_invalid_role() -> None:
      """suggested_role not a RowRole enum value → retry."""
      out = PlanVerdict(
          verdict="needs_fix",
          row_corrections=[RowCorrection(row=1, suggested_role="not_a_role")],
      )
      verdict = validate_output(out, _plan_with_rows(1))
      assert not verdict.ok
      assert "not_a_role" in verdict.reason


  def test_rejects_confidence_above_one() -> None:
      """confidence > 1 → retry."""
      out = PlanVerdict(confidence=1.5)
      verdict = validate_output(out, _plan_with_rows(1))
      assert not verdict.ok
      assert "confidence" in verdict.reason


  def test_rejects_confidence_below_zero() -> None:
      """confidence < 0 → retry."""
      out = PlanVerdict(confidence=-0.1)
      verdict = validate_output(out, _plan_with_rows(1))
      assert not verdict.ok


  def test_rejects_more_than_five_corrections() -> None:
      """>5 row_corrections → retry (prompt rule)."""
      corrs = [RowCorrection(row=i, suggested_role="anchor") for i in range(1, 7)]
      out = PlanVerdict(verdict="needs_fix", row_corrections=corrs)
      verdict = validate_output(out, _plan_with_rows(*range(1, 10)))
      assert not verdict.ok
      assert "≤5" in verdict.reason or "5" in verdict.reason


  def test_accepts_empty_corrections() -> None:
      """No corrections + looks_correct → ok."""
      assert validate_output(PlanVerdict(), _plan_with_rows(1)).ok
  ```
- [ ] Create `app/agents/plan_reviewer/validators.py`:
  ```python
  """PlanReviewer semantic validators — the load-bearing gate."""
  from __future__ import annotations

  from typing import Any

  from app.agents._base import OutputVerdict
  from app.agents.plan_reviewer.schema import PlanReviewerInputs, PlanVerdict
  from app.enums.row_role import RowRole

  _MAX_CORRECTIONS = 5
  _VALID_ROLES = {r.value for r in RowRole}


  def validate_input(inputs: PlanReviewerInputs, ctx: Any) -> OutputVerdict:
      """No-op — SheetPlan shape already enforced by Pydantic."""
      return OutputVerdict.ok()


  def validate_output(output: PlanVerdict, ctx: Any) -> OutputVerdict:
      """Reject corrections referencing absent rows, unknown roles, bad confidence, or >5 items."""
      plan = getattr(ctx, "plan", None)
      known_rows = {r.idx for r in (plan.rows if plan is not None else [])}

      if not (0.0 <= output.confidence <= 1.0):
          return OutputVerdict.retry(
              reason=f"confidence {output.confidence!r} must be in [0, 1]",
          )

      if len(output.row_corrections) > _MAX_CORRECTIONS:
          return OutputVerdict.retry(
              reason=f"row_corrections has {len(output.row_corrections)} items; "
                     f"prompt rule limits to ≤5",
          )

      for corr in output.row_corrections:
          if known_rows and corr.row not in known_rows:
              return OutputVerdict.retry(
                  reason=f"correction at row {corr.row} references non-existent row "
                         f"(plan rows: {sorted(known_rows)[:10]}...)",
              )
          if corr.suggested_role not in _VALID_ROLES:
              return OutputVerdict.retry(
                  reason=f"suggested_role {corr.suggested_role!r} is not a valid RowRole "
                         f"(expected one of {sorted(_VALID_ROLES)})",
              )

      return OutputVerdict.ok()
  ```
- [ ] Run validator tests — expect all six green.
- [ ] Commit `feat(agents): add PlanReviewer load-bearing semantic gate`.

### 3.6 Write `app/agents/plan_reviewer/agent.py`

- [ ] Write failing test `tests/unit/agents/plan_reviewer/test_agent.py`:
  ```python
  """Verify PlanReviewerAgent wiring + build_input + ctx wiring."""
  from __future__ import annotations

  from types import SimpleNamespace

  from app.agents.plan_reviewer.agent import PlanReviewerAgent
  from app.agents.plan_reviewer.schema import PlanReviewerInputs
  from app.enums.pli_mode import PliMode
  from app.enums.row_role import RowRole
  from app.models.artifacts import RowSpec, SheetPlan
  from tests.support.fake_llm import FakeLLM


  def _plan() -> SheetPlan:
      """Build a minimal SheetPlan for prompt-render tests."""
      return SheetPlan(
          sheet="Plan",
          pli_mode=PliMode.ROW_PER_PLI,
          rows=[RowSpec(idx=1, role=RowRole.HEADER), RowSpec(idx=2, role=RowRole.ANCHOR)],
      )


  def test_build_input_includes_plan_findings_peek(monkeypatch) -> None:
      """build_input renders sheet name, plan dump, tier1/2 findings, and peek."""
      from app.repositories.workbook_tools._registry import TOOL_REGISTRY
      monkeypatch.setitem(
          TOOL_REGISTRY, "peek_sheet",
          lambda ctx, sheet, rows, cols: SimpleNamespace(cells=[
              SimpleNamespace(address="A1", dtype="str", value="X"),
          ]),
      )
      agent = PlanReviewerAgent(llm=FakeLLM())
      inputs = PlanReviewerInputs(plan=_plan(), findings=[])
      text = agent.build_input(SimpleNamespace(), inputs)
      assert "# Sheet: Plan" in text
      assert "## Plan summary:" in text
      assert "A1 [str]: 'X'" in text
  ```
- [ ] Create `app/agents/plan_reviewer/agent.py`:
  ```python
  """PlanReviewer Agent — judges SheetPlan correctness."""
  from __future__ import annotations

  from typing import Any

  from app.agents._base import Agent
  from app.agents.plan_reviewer.schema import PlanReviewerInputs, PlanVerdict
  from app.agents.plan_reviewer.tuning import PlanReviewerTuning
  from app.agents.plan_reviewer.validators import validate_input, validate_output
  from app.prompts import PLAN_REVIEWER
  from app.repositories.workbook_tools._registry import TOOL_REGISTRY


  class PlanReviewerAgent(Agent[PlanReviewerInputs, PlanVerdict]):
      """Single-call LLM agent: SheetPlan + findings → PlanVerdict."""

      name = "plan_reviewer"
      prompt = PLAN_REVIEWER
      output_schema = PlanVerdict
      tuning_cls = PlanReviewerTuning
      validate_input = staticmethod(validate_input)
      validate_output = staticmethod(validate_output)

      def build_input(self, ctx: Any, inputs: PlanReviewerInputs) -> str:
          """Render sheet name, plan model_dump(json), tier-1/2 findings, and a 20x15 peek."""
          plan = inputs.plan
          peek = TOOL_REGISTRY.get("peek_sheet")
          grid = peek(ctx, plan.sheet, rows=20, cols=15)
          lines = [
              f"# Sheet: {plan.sheet}",
              "## Plan summary:",
              str(plan.model_dump(mode="json", exclude_none=True)),
              "",
              "## Tier 1/2 warnings:",
          ]
          for f in inputs.findings:
              lines.append(f"  - [{f.severity}] {f.check}: {f.message}")
          lines.append("")
          lines.append("## Sheet peek (rows 1..20, cols 1..15):")
          for c in grid.cells:
              lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
          return "\n".join(lines)
  ```
- [ ] Run agent test — expect green.
- [ ] Commit `feat(agents): add PlanReviewerAgent on new substrate`.

### 3.7 Add gate-behavior tests — load-bearing scenario

- [ ] Append to `tests/unit/agents/plan_reviewer/test_agent.py`:
  ```python
  def test_retries_when_correction_references_nonexistent_row(monkeypatch) -> None:
      """First response cites row 99 (not in plan) → retry; second response is clean."""
      from app.repositories.workbook_tools._registry import TOOL_REGISTRY
      monkeypatch.setitem(TOOL_REGISTRY, "peek_sheet",
                          lambda ctx, sheet, rows, cols: SimpleNamespace(cells=[]))
      bad = {
          "verdict": "needs_fix",
          "row_corrections": [{"row": 99, "suggested_role": "anchor"}],
          "confidence": 0.5,
      }
      good = {"verdict": "looks_correct", "confidence": 0.9}
      llm = FakeLLM.script_responses(bad, good)
      agent = PlanReviewerAgent(llm=llm)
      result = agent.run(
          SimpleNamespace(plan=_plan()),
          PlanReviewerInputs(plan=_plan()),
      )
      assert result.verdict == "looks_correct"
      assert llm.call_count == 2


  def test_retries_when_role_invalid(monkeypatch) -> None:
      """First response has unknown role → retry; second uses a valid role."""
      from app.repositories.workbook_tools._registry import TOOL_REGISTRY
      monkeypatch.setitem(TOOL_REGISTRY, "peek_sheet",
                          lambda ctx, sheet, rows, cols: SimpleNamespace(cells=[]))
      bad = {
          "verdict": "needs_fix",
          "row_corrections": [{"row": 2, "suggested_role": "captain"}],
          "confidence": 0.6,
      }
      good = {
          "verdict": "needs_fix",
          "row_corrections": [{"row": 2, "suggested_role": "anchor"}],
          "confidence": 0.6,
      }
      llm = FakeLLM.script_responses(bad, good)
      agent = PlanReviewerAgent(llm=llm)
      result = agent.run(
          SimpleNamespace(plan=_plan()),
          PlanReviewerInputs(plan=_plan()),
      )
      assert result.row_corrections[0].suggested_role == "anchor"
  ```
- [ ] Run agent tests — expect green.
- [ ] Commit `test(agents): cover PlanReviewer load-bearing gate retries`.

### 3.8 Add `Component` wrapper at `app/components/plan_reviewer.py`

- [ ] Write failing test `tests/unit/components/test_plan_reviewer_component.py`:
  ```python
  """Verify PlanReviewer component happy path + fallback."""
  from __future__ import annotations

  from types import SimpleNamespace

  from app.agents.plan_reviewer.schema import PlanVerdict
  from app.components.plan_reviewer import PlanReviewer
  from app.enums.pli_mode import PliMode
  from app.enums.row_role import RowRole
  from app.models.artifacts import RowSpec, SheetPlan
  from tests.support.fake_llm import FakeLLM


  def _plan() -> SheetPlan:
      """Minimal SheetPlan fixture."""
      return SheetPlan(
          sheet="P", pli_mode=PliMode.ROW_PER_PLI,
          rows=[RowSpec(idx=1, role=RowRole.ANCHOR)],
      )


  def test_happy_path(monkeypatch) -> None:
      """Agent returns looks_correct → component forwards verdict."""
      from app.repositories.workbook_tools._registry import TOOL_REGISTRY
      monkeypatch.setitem(TOOL_REGISTRY, "peek_sheet",
                          lambda ctx, sheet, rows, cols: SimpleNamespace(cells=[]))
      llm = FakeLLM(response={"verdict": "looks_correct", "confidence": 0.9})
      comp = PlanReviewer(llm=llm)
      out = comp.run(workbook_ctx=SimpleNamespace(), plan=_plan(), findings=[])
      assert isinstance(out["verdict"], PlanVerdict)
      assert out["verdict"].verdict == "looks_correct"


  def test_fallback(monkeypatch) -> None:
      """Agent failure → low-confidence looks_correct verdict."""
      from app.repositories.workbook_tools._registry import TOOL_REGISTRY
      monkeypatch.setitem(TOOL_REGISTRY, "peek_sheet",
                          lambda ctx, sheet, rows, cols: SimpleNamespace(cells=[]))
      llm = FakeLLM(force_failure=True)
      comp = PlanReviewer(llm=llm)
      out = comp.run(workbook_ctx=SimpleNamespace(), plan=_plan(), findings=[])
      assert out["verdict"].confidence == 0.0
  ```
- [ ] Create `app/components/plan_reviewer.py`:
  ```python
  """PlanReviewer Haystack component — wraps PlanReviewerAgent."""
  from __future__ import annotations

  from typing import Any

  from haystack import component

  from app.agents._base import AgentRunFailure
  from app.agents.plan_reviewer import PlanReviewerAgent
  from app.agents.plan_reviewer.schema import PlanReviewerInputs, PlanVerdict
  from app.core.logs import get_logger
  from app.inferencing._base import Provider
  from app.models.artifacts import SheetPlan, ValidationFinding

  log = get_logger(__name__)


  @component
  class PlanReviewer:
      """Pipeline component that reviews one SheetPlan."""

      def __init__(self, llm: Provider) -> None:
          """Construct the wrapped agent with the LLM provider."""
          self.agent = PlanReviewerAgent(llm=llm)

      @component.output_types(verdict=PlanVerdict)
      def run(self, workbook_ctx: Any, plan: SheetPlan,
              findings: list[ValidationFinding] | None = None) -> dict:
          """Run the agent; fall back to a low-confidence looks_correct on failure."""
          ctx = _ctx_with_plan(workbook_ctx, plan)
          result = self.agent.run(
              ctx, PlanReviewerInputs(plan=plan, findings=findings or []),
          )
          if isinstance(result, AgentRunFailure):
              log.warning("agent_fallback_used", agent="plan_reviewer")
              return {"verdict": PlanVerdict(verdict="looks_correct", confidence=0.0)}
          return {"verdict": result}


  def _ctx_with_plan(workbook_ctx: Any, plan: SheetPlan) -> Any:
      """Attach plan to ctx so validate_output can see plan.rows."""
      setattr(workbook_ctx, "plan", plan)
      return workbook_ctx
  ```
- [ ] Run component tests — expect green.
- [ ] Commit `feat(components): add PlanReviewer component wrapper`.

### 3.9 Update orchestrator import + simplify the `_apply_plan_review_if_needed` correction loop

- [ ] Edit `app/services/extraction.py`: change `from app.services.agents.plan_reviewer import PlanReviewer` → `from app.components.plan_reviewer import PlanReviewer`.
- [ ] Update the correction loop in `_apply_plan_review_if_needed` to read `corr.row` / `corr.suggested_role` (now typed) instead of `corr.get(...)` (since corrections are no longer raw dicts):
  ```python
  for corr in verdict.row_corrections:
      for i, r in enumerate(new_rows):
          if r.idx == corr.row:
              try:
                  suggested = RowRole(corr.suggested_role)
              except ValueError:
                  suggested = r.role
              new_rows[i] = r.model_copy(update={
                  "role": suggested,
                  "anchor_idx": corr.anchor_idx if corr.anchor_idx is not None else r.anchor_idx,
              })
              break
  ```
- [ ] Run `make test` — expect green (validators ensure suggested_role is already valid; the try/except is defensive).
- [ ] Commit `refactor(extraction): wire new PlanReviewer component`.

### 3.10 Keep `_CONFIDENCE_GATE` consistent with tuning

- [ ] In `app/services/extraction.py`, replace the module-level `_CONFIDENCE_GATE = 0.85` with a lookup from `PlanReviewerTuning()`:
  ```python
  from app.agents.plan_reviewer.tuning import PlanReviewerTuning
  _CONFIDENCE_GATE = PlanReviewerTuning().confidence_gate
  ```
- [ ] Run `make test` — expect green.
- [ ] Commit `refactor(extraction): read plan_reviewer confidence_gate from tuning`.

### 3.11 Delete old PlanReviewer code

- [ ] Delete `app/services/agents/plan_reviewer.py`.
- [ ] Delete `app/prompts/workflow/plan_reviewer.md`.
- [ ] Grep `rg "from app.services.agents.plan_reviewer|app/prompts/workflow/plan_reviewer" .` — expect zero results.
- [ ] Run `make test` — expect green.
- [ ] Commit `chore(agents): delete old plan_reviewer service module`.

### 3.12 Checkpoint — `make eval-smoke`

- [ ] Run `make eval-smoke`. Expected: matrix unchanged or improved (PlanReviewer's new gate can drop bad corrections, so improvement is plausible).
- [ ] If a row regresses, halt and investigate.
- [ ] Commit `chore(eval): confirm eval-smoke green after plan_reviewer migration` (allow-empty).

---

## Section 4 — FieldNamer migration

### 4.1 Scaffold the `app/agents/field_namer/` folder

- [ ] Create `app/agents/field_namer/__init__.py`:
  ```python
  """FieldNamer agent — maps detected labels and stage headers to canonical names."""
  from __future__ import annotations

  from app.agents.field_namer.agent import FieldNamerAgent
  from app.agents.field_namer.schema import CanonicalNameMap, FieldNamerInputs

  __all__ = ["FieldNamerAgent", "FieldNamerInputs", "CanonicalNameMap"]
  ```
- [ ] Create `app/agents/field_namer/tests/__init__.py`.
- [ ] Commit `chore(agents): scaffold field_namer folder`.

### 4.2 Move prompt to `app/prompts/field_namer.py`

- [ ] Write failing test `tests/unit/prompts/test_field_namer_prompt.py`:
  ```python
  """Verify FieldNamer prompt loads + contains canonical-name sentinels."""
  from __future__ import annotations

  from app.prompts import FIELD_NAMER


  def test_field_namer_constant_loaded() -> None:
      """FIELD_NAMER mentions canonical fields, stages, and the ignore literal."""
      assert isinstance(FIELD_NAMER, str)
      assert "FieldNamer" in FIELD_NAMER
      assert "io_number" in FIELD_NAMER
      assert "delivery_date" in FIELD_NAMER
      assert "ex_factory" in FIELD_NAMER
      assert "ignore" in FIELD_NAMER
  ```
- [ ] Create `app/prompts/field_namer.py` containing the full text of `app/prompts/workflow/field_namer.md` (lines 1–102, the body before `{{SHARED}}`) as a triple-quoted string `FIELD_NAMER`, with `{SHARED}` interpolated at the end:
  ```python
  """FieldNamer prompt — maps labels to canonical field, stage, and subfield names."""
  from __future__ import annotations

  from app.prompts._shared import SHARED

  FIELD_NAMER: str = f"""You are FieldNamer. Map supplier labels, stage column headers, and stage
  sub-field labels to canonical names.

  ## Canonical PLI field names (top-level fields on every PLI)

  These names populate the PLI directly — `pli.io_number`, `pli.quantity`, etc.
  **Always prefer these over their metadata-bound aliases when both could apply.**

    io_number, style_code, style_name, color_code, color_name, fabric_code,
    delivery_date, quantity

  ## Other canonical names (land in pli.metadata, not on the PLI itself)

  These are valid canonicals but they do NOT have a dedicated PLI field — they
  land in `pli.metadata[<canonical>]`. Use them only when the cell content
  genuinely does not match one of the 8 PLI-field canonicals above.

    order_receipt_date, pps_completion, sample_completion, ex_factory_date,
    buyer, season, factory, article_no, price, balance_qty, buyer_po_no,
    fabric_quality, cut_qty, sewing_qty, shipped_qty, etd_ex_factory,
    sample_dispatch

  ## PLI-field-preference rule (load-bearing)

  When a column's cell content matches the semantic of a PLI canonical, ALWAYS
  map to the PLI canonical, NOT to a more specific metadata-bound canonical:

    - "Order Qty", "Plan Qty", "Required Qty", "Cut Qty Plan" → quantity
      (NOT order_quantity / plan_quantity / cut_qty when they hold the order amount)
    - "Etd Ex factory as per P.O", "Etd", "ETA", "Ex Factory Date",
      "Delivery Date" → delivery_date
      (NOT etd_ex_factory / ex_factory_date)
    - "Fabric Quality", "Material Quality", "Fabric Type", "Fabric Description" →
      fabric_code when the cell holds a fabric description like "100% COTTON 30S"
      (NOT fabric_quality)
    - "Buyer Po No", "Buyer PO" → io_number when it is the primary per-row
      identifier (use buyer_po_no only when a separate io_number column also exists)

  The general principle: every column that holds a "quantity" should populate
  `pli.quantity`; every column that holds a "delivery date" should populate
  `pli.delivery_date`; every column that holds a "fabric description" should
  populate `pli.fabric_code`. Don't fragment the same logical concept across
  multiple metadata buckets.

  ## Canonical stage names (drop into Stage.name)

    fabric, lab_dip_send, lab_dip_approval, fit_send, fit_approval,
    art_work_send, art_work_approval, in_house_fabric_send,
    in_house_fabric_approval, pre_production_send, pre_production_approval,
    first_pattern, garment_pattern, planned_completion_date,
    size_set, lot_card, cutting, feeding, sewing, sewing_start, sewing_end,
    final_inspection, printing, embroidery, washing, finishing, packing,
    ex_factory, trims_inhouse

  ## Stage-name guard rule (load-bearing)

  Stage names MUST be drawn from the canonical stage name list ONLY. NEVER use a
  PLI canonical field name (e.g. `ex_factory_date`, `delivery_date`,
  `fabric_code`) as a stage name. If a stage header looks like a PLI field name
  or has no matching stage canonical, map it to `ignore`.

  Examples:
    - "Ex Factory Shipment", "Ex-Factory", "Shipment" → ex_factory
      (NOT ex_factory_date — that's a PLI field name)
    - "Sewing Start" → sewing_start (NOT feeding — different operation)
    - "Sewing End" → sewing_end
    - "Final Inspection", "FI", "Inspection" → final_inspection
    - "Trims Inhouse" → trims_inhouse (NOT in_house_fabric_send — trims and fabric
      are separate procurement streams)

  ## Canonical stage sub-field names (for wide_sub_columns with sub-cols)

    planned_date, actual_date, approval_date, received_date,
    approved_qty, quantity, remarks, comments, deviation_days

  ## Output JSON matching CanonicalNameMap

  - field_labels: {{original_label: canonical_field_name | "ignore"}}
  - stage_names: {{original_stage_header: canonical_stage_name | "ignore"}}
  - stage_subfield_labels: {{original_sub_label: canonical_subfield | "ignore"}}
  - field_confidence: optional {{canonical_field: 0.0–1.0}}
  - stage_confidence: optional {{canonical_stage: 0.0–1.0}}

  Use "ignore" for labels that aren't worth extracting.

  ## Inference from sample values

  When you see sample values in parentheses after a label, use them to infer the
  canonical name when the label itself is ambiguous (e.g. a 4-digit integer
  column with values like 1063 is likely io_number even if the label is "Job #").

  ## Label disambiguation rules

  - "Buyer Po No", "Buyer PO", "PO No", "PO Number", "Order No", "Order Ref" →
    prefer io_number when it is the primary per-row PLI identifier.
    Use buyer_po_no only when a separate io_number field is also present.
  - "Style No", "Style Number", "Style Code", "Art No", "Article No" → style_code.
  - Bare "STYLE": if the sample value contains a combined code+name pattern
    (e.g. "890162 TAVIRA_2 522148" or "STYLE_NAME / STYLE-CODE"), map to
    style_code. If samples are pure descriptive names (e.g. "D-T-SHIRT 3/4"),
    map to style_name.

  {SHARED}
  """
  ```
  Note: every literal `{` and `}` inside f-string body is doubled (`{{` / `}}`) — keep the `{SHARED}` placeholder single-braced.
- [ ] Update `app/prompts/__init__.py` to add `from app.prompts.field_namer import FIELD_NAMER`.
- [ ] Run prompt test — expect green.
- [ ] Commit `refactor(prompts): move field_namer prompt to python module`.

### 4.3 Move CanonicalNameMap schema to `app/agents/field_namer/schema.py`

- [ ] Write failing test `tests/unit/agents/field_namer/test_schema.py`:
  ```python
  """Verify FieldNamer input + output schemas."""
  from __future__ import annotations

  from app.agents.field_namer.schema import CanonicalNameMap, FieldNamerInputs
  from app.enums.pli_mode import PliMode
  from app.models.artifacts import SheetPlan


  def test_canonical_name_map_defaults() -> None:
      """CanonicalNameMap defaults to all-empty + None decision_notes."""
      m = CanonicalNameMap()
      assert m.field_labels == {}
      assert m.stage_names == {}
      assert m.stage_subfield_labels == {}
      assert m.field_confidence == {}
      assert m.stage_confidence == {}
      assert m.decision_notes is None


  def test_inputs_wraps_plan() -> None:
      """FieldNamerInputs holds the SheetPlan."""
      plan = SheetPlan(sheet="P", pli_mode=PliMode.ROW_PER_PLI)
      inputs = FieldNamerInputs(plan=plan)
      assert inputs.plan.sheet == "P"
  ```
- [ ] Create `app/agents/field_namer/schema.py`:
  ```python
  """FieldNamer I/O schemas."""
  from __future__ import annotations

  from pydantic import BaseModel, ConfigDict, Field

  from app.models.artifacts import SheetPlan


  class FieldNamerInputs(BaseModel):
      """Inputs to FieldNamer — wraps a SheetPlan."""

      model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)
      plan: SheetPlan


  class CanonicalNameMap(BaseModel):
      """FieldNamer's output — labels mapped to canonical names + per-label confidence."""

      model_config = ConfigDict(extra="ignore")
      field_labels: dict[str, str] = Field(default_factory=dict)
      stage_names: dict[str, str] = Field(default_factory=dict)
      stage_subfield_labels: dict[str, str] = Field(default_factory=dict)
      field_confidence: dict[str, float] = Field(default_factory=dict)
      stage_confidence: dict[str, float] = Field(default_factory=dict)
      decision_notes: str | None = None
  ```
- [ ] In `app/models/artifacts.py`: delete the original `class CanonicalNameMap`; add `from app.agents.field_namer.schema import CanonicalNameMap  # noqa: F401`.
- [ ] Run schema tests — expect green.
- [ ] Commit `refactor(agents): move CanonicalNameMap schema to agent folder`.

### 4.4 Write `app/agents/field_namer/tuning.py` with canonical-name lists

- [ ] Write failing test `tests/unit/agents/field_namer/test_tuning.py`:
  ```python
  """Verify FieldNamerTuning carries canonical-name allow-lists."""
  from __future__ import annotations

  from app.agents.field_namer.tuning import FieldNamerTuning


  def test_canonical_lists_complete() -> None:
      """Allow-lists include PLI fields, metadata canonicals, stages, subfields."""
      t = FieldNamerTuning()
      assert "io_number" in t.canonical_pli_fields
      assert "quantity" in t.canonical_pli_fields
      assert "ex_factory_date" in t.canonical_metadata_fields
      assert "ex_factory" in t.canonical_stage_names
      assert "planned_date" in t.canonical_subfield_names
      assert t.max_retries == 1
      assert t.capture_decision_notes is False


  def test_combined_field_allowlist_includes_both_groups() -> None:
      """combined_field_canonicals merges PLI and metadata groups."""
      t = FieldNamerTuning()
      both = t.combined_field_canonicals
      assert "io_number" in both  # from PLI
      assert "buyer" in both  # from metadata
  ```
- [ ] Create `app/agents/field_namer/tuning.py`:
  ```python
  """FieldNamer tuning knobs — also the source of truth for canonical name lists."""
  from __future__ import annotations

  from pydantic import Field, computed_field
  from pydantic_settings import BaseSettings, SettingsConfigDict


  class FieldNamerTuning(BaseSettings):
      """Per-agent tuning for FieldNamer; canonical lists drive validate_output."""

      model_config = SettingsConfigDict(env_prefix="TNA_FIELD_NAMER_", extra="ignore")

      max_retries: int = 1
      capture_decision_notes: bool = False
      confidence_gate: float = 0.0  # FieldNamer self-reports per-label confidence only

      canonical_pli_fields: list[str] = Field(default_factory=lambda: [
          "io_number", "style_code", "style_name", "color_code", "color_name",
          "fabric_code", "delivery_date", "quantity",
      ])
      canonical_metadata_fields: list[str] = Field(default_factory=lambda: [
          "order_receipt_date", "pps_completion", "sample_completion",
          "ex_factory_date", "buyer", "season", "factory", "article_no",
          "price", "balance_qty", "buyer_po_no", "fabric_quality", "cut_qty",
          "sewing_qty", "shipped_qty", "etd_ex_factory", "sample_dispatch",
      ])
      canonical_stage_names: list[str] = Field(default_factory=lambda: [
          "fabric", "lab_dip_send", "lab_dip_approval", "fit_send", "fit_approval",
          "art_work_send", "art_work_approval", "in_house_fabric_send",
          "in_house_fabric_approval", "pre_production_send", "pre_production_approval",
          "first_pattern", "garment_pattern", "planned_completion_date",
          "size_set", "lot_card", "cutting", "feeding", "sewing", "sewing_start",
          "sewing_end", "final_inspection", "printing", "embroidery", "washing",
          "finishing", "packing", "ex_factory", "trims_inhouse",
      ])
      canonical_subfield_names: list[str] = Field(default_factory=lambda: [
          "planned_date", "actual_date", "approval_date", "received_date",
          "approved_qty", "quantity", "remarks", "comments", "deviation_days",
      ])

      semantic_examples: list[dict] = Field(default_factory=list)
      anti_pattern_examples: list[dict] = Field(default_factory=list)

      @computed_field
      @property
      def combined_field_canonicals(self) -> set[str]:
          """Union of PLI + metadata canonical names — the full field-label allow-list."""
          return set(self.canonical_pli_fields) | set(self.canonical_metadata_fields)
  ```
- [ ] Run tuning tests — expect green.
- [ ] Commit `feat(agents): add FieldNamer tuning with canonical-name lists`.

### 4.5 Write `app/agents/field_namer/validators.py`

- [ ] Write failing test `tests/unit/agents/field_namer/test_validators.py`:
  ```python
  """Verify FieldNamer validate_output rejects non-canonical names."""
  from __future__ import annotations

  from types import SimpleNamespace

  from app.agents.field_namer.schema import CanonicalNameMap
  from app.agents.field_namer.validators import validate_output


  def test_accepts_canonical_field_names() -> None:
      """All values come from the canonical lists."""
      out = CanonicalNameMap(
          field_labels={"Job No": "io_number", "Total": "ignore"},
          stage_names={"Cutting": "cutting"},
          stage_subfield_labels={"Plan": "planned_date"},
      )
      verdict = validate_output(out, SimpleNamespace())
      assert verdict.ok


  def test_rejects_invented_field() -> None:
      """A field_label value not in canonical lists → retry."""
      out = CanonicalNameMap(field_labels={"X": "made_up_canonical"})
      verdict = validate_output(out, SimpleNamespace())
      assert not verdict.ok
      assert "made_up_canonical" in verdict.reason
      assert "canonical" in verdict.reason


  def test_rejects_pli_field_used_as_stage_name() -> None:
      """Stage name set to a PLI field (e.g. ex_factory_date) → retry."""
      out = CanonicalNameMap(stage_names={"Shipment": "ex_factory_date"})
      verdict = validate_output(out, SimpleNamespace())
      assert not verdict.ok
      assert "ex_factory_date" in verdict.reason


  def test_rejects_invented_subfield() -> None:
      """Subfield value not in canonical_subfield_names → retry."""
      out = CanonicalNameMap(stage_subfield_labels={"Plan": "weird_sub"})
      verdict = validate_output(out, SimpleNamespace())
      assert not verdict.ok
      assert "weird_sub" in verdict.reason


  def test_ignore_is_always_accepted() -> None:
      """The literal 'ignore' is accepted in every channel."""
      out = CanonicalNameMap(
          field_labels={"X": "ignore"},
          stage_names={"X": "ignore"},
          stage_subfield_labels={"X": "ignore"},
      )
      assert validate_output(out, SimpleNamespace()).ok
  ```
- [ ] Create `app/agents/field_namer/validators.py`:
  ```python
  """FieldNamer semantic validators — every value must be canonical or 'ignore'."""
  from __future__ import annotations

  from typing import Any

  from app.agents._base import OutputVerdict
  from app.agents.field_namer.schema import CanonicalNameMap, FieldNamerInputs
  from app.agents.field_namer.tuning import FieldNamerTuning


  _IGNORE = "ignore"


  def validate_input(inputs: FieldNamerInputs, ctx: Any) -> OutputVerdict:
      """No-op input validation — SheetPlan shape already enforced by Pydantic."""
      return OutputVerdict.ok()


  def validate_output(output: CanonicalNameMap, ctx: Any) -> OutputVerdict:
      """Reject any value not in the agent's canonical allow-lists (or 'ignore')."""
      tuning = FieldNamerTuning()
      fields_ok = tuning.combined_field_canonicals
      stages_ok = set(tuning.canonical_stage_names)
      subs_ok = set(tuning.canonical_subfield_names)

      bad = _first_bad(output.field_labels, fields_ok, "field_labels")
      if bad is not None:
          return _retry(bad, sorted(fields_ok))
      bad = _first_bad(output.stage_names, stages_ok, "stage_names")
      if bad is not None:
          return _retry(bad, sorted(stages_ok))
      bad = _first_bad(output.stage_subfield_labels, subs_ok, "stage_subfield_labels")
      if bad is not None:
          return _retry(bad, sorted(subs_ok))
      return OutputVerdict.ok()


  def _first_bad(mapping: dict[str, str], allowed: set[str],
                 channel: str) -> tuple[str, str, str] | None:
      """Return (channel, original_label, bad_canonical) for the first violator, or None."""
      for raw, canonical in mapping.items():
          if canonical == _IGNORE:
              continue
          if canonical not in allowed:
              return (channel, raw, canonical)
      return None


  def _retry(bad: tuple[str, str, str], allowed_sorted: list[str]) -> OutputVerdict:
      """Format a retry verdict naming the bad mapping and the allow-list."""
      channel, raw, canonical = bad
      return OutputVerdict.retry(
          reason=f"{channel}[{raw!r}] = {canonical!r} is not a canonical name; "
                 f"please pick from list or 'ignore'. Allowed: {allowed_sorted}",
      )
  ```
- [ ] Run validator tests — expect green.
- [ ] Commit `feat(agents): add FieldNamer canonical-name semantic gate`.

### 4.6 Write `app/agents/field_namer/agent.py` — preserve multi-channel build_input

- [ ] Write failing test `tests/unit/agents/field_namer/test_agent.py`:
  ```python
  """Verify FieldNamerAgent renders identity + stages + subfields + samples."""
  from __future__ import annotations

  from types import SimpleNamespace

  from app.agents.field_namer.agent import FieldNamerAgent
  from app.agents.field_namer.schema import FieldNamerInputs
  from app.enums.pli_mode import PliMode
  from app.enums.row_role import RowRole
  from app.models.artifacts import (
      HeaderLabel, KVAnchor, PliBlock, RowSpec, SheetPlan, StageBandSpec, StageColumn,
  )
  from tests.support.fake_llm import FakeLLM


  def test_build_input_includes_identity_stage_sub_channels() -> None:
      """build_input emits identity labels, stage names, and sub-field labels."""
      plan = SheetPlan(
          sheet="Plan",
          pli_mode=PliMode.ROW_PER_PLI,
          rows=[RowSpec(idx=2, role=RowRole.ANCHOR)],
          header_labels=[HeaderLabel(raw="Job No", col="A")],
          stage_bands=[StageBandSpec(
              sub_header_row=1, stage_cols={},
              stage_columns=[StageColumn(name="Cutting", name_cell="C1", primary_col="C",
                                          sub_columns={"Plan": "C", "Actual": "D"})],
          )],
      )
      agent = FieldNamerAgent(llm=FakeLLM())
      text = agent.build_input(SimpleNamespace(), FieldNamerInputs(plan=plan))
      assert "## Identity labels detected:" in text
      assert "'Job No'" in text
      assert "## Stage headers detected:" in text
      assert "'Cutting'" in text
      assert "## Stage sub-field labels detected:" in text
      assert "'Plan'" in text


  def test_build_input_includes_kv_anchors_for_sheet_is_pli() -> None:
      """SHEET_IS_PLI mode pulls labels from kv_anchors."""
      plan = SheetPlan(
          sheet="P",
          pli_mode=PliMode.SHEET_IS_PLI,
          kv_anchors=[KVAnchor(field="Buyer PO", label_cell="B3", value_cell="C3")],
      )
      agent = FieldNamerAgent(llm=FakeLLM())
      text = agent.build_input(SimpleNamespace(), FieldNamerInputs(plan=plan))
      assert "'Buyer PO'" in text


  def test_build_input_pulls_block_identity_for_section_per_pli() -> None:
      """SECTION_PER_PLI mode pulls labels from pli_blocks[].identity."""
      plan = SheetPlan(
          sheet="P",
          pli_mode=PliMode.SECTION_PER_PLI,
          pli_blocks=[PliBlock(
              start_row=3, end_row=10,
              identity=[KVAnchor(field="IO", label_cell="B3", value_cell="C3")],
              stage_bands=[],
          )],
      )
      agent = FieldNamerAgent(llm=FakeLLM())
      text = agent.build_input(SimpleNamespace(), FieldNamerInputs(plan=plan))
      assert "'IO'" in text
  ```
- [ ] Create `app/agents/field_namer/agent.py` (port the existing helpers verbatim into the agent module so behaviour is preserved):
  ```python
  """FieldNamer Agent — multi-channel label-to-canonical mapping."""
  from __future__ import annotations

  from typing import Any

  from openpyxl.utils import column_index_from_string
  from openpyxl.utils.cell import coordinate_from_string

  from app.agents._base import Agent
  from app.agents.field_namer.schema import CanonicalNameMap, FieldNamerInputs
  from app.agents.field_namer.tuning import FieldNamerTuning
  from app.agents.field_namer.validators import validate_input, validate_output
  from app.enums.pli_mode import PliMode
  from app.models.artifacts import SheetPlan, StageBandSpec, StageColumn
  from app.prompts import FIELD_NAMER


  class FieldNamerAgent(Agent[FieldNamerInputs, CanonicalNameMap]):
      """Single-call LLM agent: SheetPlan → CanonicalNameMap (multi-channel)."""

      name = "field_namer"
      prompt = FIELD_NAMER
      output_schema = CanonicalNameMap
      tuning_cls = FieldNamerTuning
      validate_input = staticmethod(validate_input)
      validate_output = staticmethod(validate_output)

      def build_input(self, ctx: Any, inputs: FieldNamerInputs) -> str:
          """Render identity + stage + subfield channels for one SheetPlan."""
          plan = inputs.plan
          ws = ctx.wb[plan.sheet] if hasattr(ctx, "wb") else None

          identity: list[tuple[str, str]] = [(hl.raw, hl.col) for hl in plan.header_labels]
          identity.extend((kv.field, _col_of(kv.label_cell)) for kv in plan.kv_anchors)
          for blk in plan.pli_blocks:
              identity.extend((kv.field, _col_of(kv.label_cell)) for kv in blk.identity)

          stage_names: list[str] = []
          sub_labels: set[str] = set()
          all_bands = list(plan.stage_bands)
          for blk in plan.pli_blocks:
              all_bands.extend(blk.stage_bands)
          for band in all_bands:
              for sc in band.stage_columns or _legacy_columns(band):
                  stage_names.append(sc.name)
                  sub_labels.update(sc.sub_columns.keys())

          samples = _sample_values(ws, plan, identity, k=3) if ws is not None else {}
          return _format_markdown(plan.sheet, identity, stage_names, sub_labels, samples)


  def _col_of(addr: str) -> str:
      """Return the column letter from a cell address like 'AA12'."""
      col_letter, _ = coordinate_from_string(addr)
      return col_letter


  def _legacy_columns(band: StageBandSpec) -> list[StageColumn]:
      """Build StageColumn list from a band's legacy `stage_cols` dict."""
      return [
          StageColumn(name=name, name_cell=f"{col}{band.sub_header_row}", primary_col=col)
          for name, col in band.stage_cols.items()
      ]


  def _format_markdown(sheet: str, identity: list[tuple[str, str]],
                       stage_names: list[str], sub_labels: set[str],
                       samples: dict[str, list[object]]) -> str:
      """Render a deterministic markdown prompt body."""
      lines = [f"# Sheet: {sheet}", "", "## Identity labels detected:"]
      for raw, col in sorted(set(identity)):
          blurb = ""
          if samples.get(raw):
              blurb = "  samples: " + ", ".join(repr(s) for s in samples[raw][:3])
          lines.append(f"  - {raw!r} (col {col}){blurb}")
      lines.append("")
      lines.append("## Stage headers detected:")
      for name in sorted(set(stage_names)):
          lines.append(f"  - {name!r}")
      if sub_labels:
          lines.append("")
          lines.append("## Stage sub-field labels detected:")
          for sub in sorted(sub_labels):
              lines.append(f"  - {sub!r}")
      return "\n".join(lines)


  def _sample_values(ws, plan: SheetPlan, identity: list[tuple[str, str]],
                     k: int = 3) -> dict[str, list[object]]:
      """Return up to k non-null sample values per ROW_PER_PLI identity label."""
      if plan.pli_mode is not PliMode.ROW_PER_PLI:
          return {}
      data_rows = [r.idx for r in plan.rows if r.role.value in {"anchor", "child"}]
      if not data_rows:
          return {}
      out: dict[str, list[object]] = {}
      for raw, col in identity:
          col_idx = column_index_from_string(col)
          seen: list[object] = []
          for r in data_rows:
              if len(seen) >= k:
                  break
              v = ws.cell(row=r, column=col_idx).value
              if v is None:
                  continue
              if isinstance(v, str) and len(v) > 60:
                  v = v[:57] + "..."
              seen.append(v)
          if seen:
              out[raw] = seen
      return out
  ```
- [ ] Run agent tests — expect all three green.
- [ ] Commit `feat(agents): add FieldNamerAgent on new substrate`.

### 4.7 Add gate-behavior tests

- [ ] Append to `tests/unit/agents/field_namer/test_agent.py`:
  ```python
  def test_retries_when_canonical_name_invented() -> None:
      """First response invents 'made_up' → retry; second response uses 'ignore'."""
      plan = SheetPlan(
          sheet="P", pli_mode=PliMode.ROW_PER_PLI,
          header_labels=[HeaderLabel(raw="X", col="A")],
      )
      bad = {"field_labels": {"X": "made_up_canonical"}}
      good = {"field_labels": {"X": "ignore"}}
      llm = FakeLLM.script_responses(bad, good)
      agent = FieldNamerAgent(llm=llm)
      result = agent.run(SimpleNamespace(), FieldNamerInputs(plan=plan))
      assert result.field_labels == {"X": "ignore"}
      assert llm.call_count == 2


  def test_retries_when_pli_field_used_as_stage() -> None:
      """First response sets stage_names[X]='ex_factory_date' → retry."""
      plan = SheetPlan(sheet="P", pli_mode=PliMode.ROW_PER_PLI)
      bad = {"stage_names": {"X": "ex_factory_date"}}
      good = {"stage_names": {"X": "ex_factory"}}
      llm = FakeLLM.script_responses(bad, good)
      agent = FieldNamerAgent(llm=llm)
      result = agent.run(SimpleNamespace(), FieldNamerInputs(plan=plan))
      assert result.stage_names == {"X": "ex_factory"}
  ```
- [ ] Run agent tests — expect green.
- [ ] Commit `test(agents): cover FieldNamer canonical-gate retries`.

### 4.8 Add `Component` wrapper at `app/components/field_namer.py`

- [ ] Write failing test `tests/unit/components/test_field_namer_component.py`:
  ```python
  """Verify FieldNamer component happy path + fallback."""
  from __future__ import annotations

  from types import SimpleNamespace

  from app.agents.field_namer.schema import CanonicalNameMap
  from app.components.field_namer import FieldNamer
  from app.enums.pli_mode import PliMode
  from app.models.artifacts import SheetPlan
  from tests.support.fake_llm import FakeLLM


  def _plan() -> SheetPlan:
      """Minimal SheetPlan fixture."""
      return SheetPlan(sheet="P", pli_mode=PliMode.ROW_PER_PLI)


  def test_happy_path() -> None:
      """Agent returns a name map → component forwards it."""
      llm = FakeLLM(response={"field_labels": {"Job No": "io_number"}})
      comp = FieldNamer(llm=llm)
      out = comp.run(workbook_ctx=SimpleNamespace(), plan=_plan())
      assert isinstance(out["name_map"], CanonicalNameMap)
      assert out["name_map"].field_labels == {"Job No": "io_number"}


  def test_fallback() -> None:
      """Agent failure → empty CanonicalNameMap."""
      llm = FakeLLM(force_failure=True)
      comp = FieldNamer(llm=llm)
      out = comp.run(workbook_ctx=SimpleNamespace(), plan=_plan())
      assert out["name_map"].field_labels == {}
  ```
- [ ] Create `app/components/field_namer.py`:
  ```python
  """FieldNamer Haystack component — wraps FieldNamerAgent."""
  from __future__ import annotations

  from typing import Any

  from haystack import component

  from app.agents._base import AgentRunFailure
  from app.agents.field_namer import FieldNamerAgent
  from app.agents.field_namer.schema import CanonicalNameMap, FieldNamerInputs
  from app.core.logs import get_logger
  from app.inferencing._base import Provider
  from app.models.artifacts import SheetPlan

  log = get_logger(__name__)


  @component
  class FieldNamer:
      """Pipeline component that maps labels to canonical names for one SheetPlan."""

      def __init__(self, llm: Provider) -> None:
          """Construct the wrapped agent with the LLM provider."""
          self.agent = FieldNamerAgent(llm=llm)

      @component.output_types(name_map=CanonicalNameMap)
      def run(self, workbook_ctx: Any, plan: SheetPlan) -> dict:
          """Run the agent; fall back to empty CanonicalNameMap on failure."""
          result = self.agent.run(workbook_ctx, FieldNamerInputs(plan=plan))
          if isinstance(result, AgentRunFailure):
              log.warning("agent_fallback_used", agent="field_namer")
              return {"name_map": CanonicalNameMap()}
          return {"name_map": result}
  ```
- [ ] Run component tests — expect green.
- [ ] Commit `feat(components): add FieldNamer component wrapper`.

### 4.9 Update orchestrator import

- [ ] Edit `app/services/extraction.py`: change `from app.services.agents.field_namer import FieldNamer` → `from app.components.field_namer import FieldNamer`.
- [ ] Run `make test` — expect green.
- [ ] Commit `refactor(extraction): wire new FieldNamer component`.

### 4.10 Delete old FieldNamer code

- [ ] Delete `app/services/agents/field_namer.py`.
- [ ] Delete `app/prompts/workflow/field_namer.md`.
- [ ] Grep `rg "from app.services.agents.field_namer|app/prompts/workflow/field_namer" .` — expect zero results.
- [ ] Run `make test` — expect green.
- [ ] Commit `chore(agents): delete old field_namer service module`.

### 4.11 Checkpoint — `make eval-smoke`

- [ ] Run `make eval-smoke`. Expected: matrix unchanged or improved (canonical-gate prevents invented names that previously polluted name maps).
- [ ] If regression, halt and investigate (FieldNamer is the biggest semantic-coverage agent).
- [ ] Commit `chore(eval): confirm eval-smoke green after field_namer migration` (allow-empty).

---

## Section 5 — Final full-matrix eval checkpoint

### 5.1 Confirm `app/services/agents/` is empty of agent modules

- [ ] Run `ls app/services/agents/`. Expected: `__init__.py` and `_base.py` only (the `_base.py` retires in sub-plan 5).
- [ ] Run `rg "app.prompts.workflow" .` and `rg "from app.services.agents.(sheet_classifier|layout_hinter|plan_reviewer|field_namer)" .` — both expect zero hits.
- [ ] Commit `chore(agents): verify old agent modules removed` (allow-empty if no file changes).

### 5.2 Run full `make eval` and compare to pre-migration baseline

- [ ] Snapshot the pre-migration eval matrix from the most recent `evals/runs/<latest>/matrix.json` (or whatever the current eval output is) into `evals/runs/_pre_migration_baseline.json` before starting Section 1. (If this baseline was not captured, capture it before running this step against the *current* matrix.)
- [ ] Run `make eval`. Expected output: matrix shows status_rate, field_coverage, and stage_coverage equal to or higher than the baseline for every dataset row. No row may regress.
- [ ] Diff the new matrix against the baseline and paste the summary in the commit body.
- [ ] If any row regresses, halt: open an investigation task; do not proceed to sub-plan 5 until the regression is understood and accepted or fixed.
- [ ] Commit `chore(eval): confirm full eval green after sub-plan 4 migrations`.

### 5.3 Self-review the plan completion

- [ ] Confirm every spec requirement is covered:
  - §3 seven-primitives mapping (agent + component + prompts + tuning_params): ✅ all four migrations created `app/agents/<name>/`, `app/components/<name>.py`, `app/prompts/<name>.py`, `app/agents/<name>/tuning.py`.
  - §5 lifecycle (validate_input + validate_output + retry-with-reason): ✅ all four agents wrote validators and have gate-retry tests.
  - §6 file-by-file mapping for the four agents: ✅ `app/services/agents/<name>.py` → `app/agents/<name>/agent.py`; `app/prompts/workflow/<name>.md` → `app/prompts/<name>.py`; schemas moved into `app/agents/<name>/schema.py` with back-compat shim in `app/models/artifacts.py`.
  - §10 sub-plan 4 per-agent steps (1–6 plus per-agent eval-smoke + per-agent exit criterion): ✅ each section runs `make test` + `make eval-smoke` at completion.
- [ ] Confirm orchestrator (`app/services/extraction.py`) is fully re-wired to new component paths.
- [ ] Confirm exit criterion per the spec: "eval matrix unchanged or improved; new agent-tier tests cover gate behaviour" — Section 5.2's full-matrix diff covers the former; the per-agent gate-retry tests (1.8, 2.8, 3.7, 4.7) cover the latter.
- [ ] Commit `docs(plans): close out sub-plan 4 self-review` (allow-empty).
