---
name: M0 foundation implementation complete (2026-05-09)
description: Status of the tna_parser experiment package after the M0 plan finished — what's built, what's tested, what's left
type: project
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
The M0 foundation plan (`F:\DAITA\ARENA\TNA\TNA AI parser\05-plans\2026-05-08-m0-foundation-and-baseline.md`) is complete as of 2026-05-09. All 12 tasks landed.

## What's built

`F:\DAITA\ARENA\TNA\tna_parser\` (src layout):
- `models.py` — Pydantic models: workbook (`Cell`, `MergedRegion`, `CellGrid` with `cell_range` field, `SheetMeta`) + output (`Stage`, `PLI` w/ `quantity` + `color_name`, `Warning`, `ExtractionResult` w/ string-warning coercion validator)
- `workbook.py` — `register_workbook` + `WorkbookCtx` w/ single-open caching
- `tools.py` — `list_sheets`, `get_full_grid` (capped at 5000 cells, merge metadata included)
- `anthropic_client.py` — `AnthropicClient` w/ `complete_with_schema` via tool use; `schema_to_tool` Pydantic→tool converter; upward-walking `.env` search
- `baseline.py` — `run_baseline` + `build_baseline_prompt`; the mandatory single-prompt control
- `eval.py` — `load_label`, `score_against_label`, `EvalReport`, `FieldDiff`; field + stage diff against `dataset/extracted/*.json`
- `cli.py` — `tna-parser parse <file>` + `tna-parser eval <file> --label <path>`

## Test status

**66 offline unit + integration tests passing**, distributed across:
- `test_models.py` (13) — Pydantic schemas + label parsing
- `test_workbook.py` (5) — workbook context caching
- `test_tools.py` (8) — list_sheets + get_full_grid
- `test_anthropic_client.py` (6) — schema-to-tool, env handling
- `test_baseline.py` (4) — prompt construction + result wiring (mocked)
- `test_eval.py` (6) — score_against_label edge cases
- `test_label_compat.py` (20) — parametrized: every JSON in `dataset/extracted/` parses + round-trips
- `test_cli.py` (4) — parse/eval subcommands

**Live baseline run captured** — see `m0_baseline_results.md`.

## Deferred follow-ups (non-blocking, tracked but not done)

From code reviews during the plan, deferred to a polish pass / final review:

1. `WorkbookCtx.close()` + `clear_cache` should call it on each entry (Windows GC pressure could leave file handles open).
2. `register_workbook` should guard against non-`.xlsx` paths with a clear `ValueError` (currently raises a confusing `BadZipFile`).
3. `WorkbookCtx.__init__` could use a one-line docstring.
4. `_CACHE` type annotation could lose its forward-reference string by reordering class above dict.
5. `test_register_workbook_returns_ctx` hardcodes sheet names — could move to a conftest constant.
6. `Cell.value` / `MergedRegion.anchor_value` typed `Any` — could tighten to a value union now that schema is settled.
7. `Cell.address` has no A1-format validator — mismatch with row/col is unenforced.
8. `requirements.txt` includes dev deps (pytest, pytest-asyncio); user has accepted this for the experiment phase.

## What's NOT built (intentionally — follow-up plan)

- The 8 specialist agents (Inspector, Sheet Triager, Layout Classifier, Field Locator, Stage Locator, PLI Boundary Finder, Validator, Generic Explorer)
- LangGraph orchestrator + state graph
- Bridge artifacts (`FieldMap`, `StageBand`, `StageBandSet`, `PLIBoundaries`)
- Deterministic appliers (`apply_field_map`, `apply_stage_band_set`)
- Multi-format coverage (only DKN labeled-baseline run so far)
- Parallel-sheet optimization
- `find_value`, `peek_sheet`, `sample_rows`, `read_range`, `read_row`, `read_col`, `read_cell`, `read_relative`, `read_anchor_block`, `get_merged_regions`, `count_data_rows`, `detect_section_breaks` (the rest of the tool surface from design §3.2)

These are scoped for the next plan, which the user will write/dispatch when ready.

## How to use what's built

```powershell
cd F:\DAITA\ARENA\TNA

# Run baseline against any file in the dataset
.\.venv\Scripts\python.exe -m tna_parser.cli parse "dataset\<filename>.xlsx" --out "<output>.json"

# Score baseline against a label
.\.venv\Scripts\python.exe -m tna_parser.cli eval "dataset\<filename>.xlsx" --label "dataset\extracted\<filename>.json"

# Run all unit/integration tests
.\.venv\Scripts\python.exe -m pytest tna_parser/tests -v
```
