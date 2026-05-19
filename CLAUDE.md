# TNA Service — Claude Code Context

## Identity

TNA Service is a production-shaped FastAPI microservice that parses Excel TNA (Time and Action) spreadsheets into structured PLI JSON using a multi-agent LLM pipeline backed by deterministic helpers. It is the operational successor to the `tna_parser` experiment package.

## Current state (as of 2026-05-19)

Production-shaped, not yet deployed. The SheetRowPlanner pipeline now feeds
FieldNamer and apply_plan symmetrically across all three `pli_mode`s via the
extended `SheetPlan` artifact contract (ADR-0006): `header_labels` for
ROW_PER_PLI, `kv_anchors` for SHEET_IS_PLI, `pli_blocks[].identity` for
SECTION_PER_PLI. `StageBandSpec.stage_columns` carries per-stage `sub_columns`
for wide_sub_columns layouts. `apply_plan` writes per-field `PLI.confidence`.
Test count: 248 passing (non-live). Live regression passes for Christian
Berg, DKN, and Northern Reflections; FA26 (Family 5 TOTAL-footers) is xfailed
pending a mode-decision follow-up.

## Orientation map

| Want to know | Read |
|---|---|
| Full narrative arc (how we got here) | `docs/JOURNEY.md` |
| Principles + rules | `docs/PRINCIPLES.md` |
| Major architectural decisions | `docs/adrs/` |
| Current technical architecture | `ARCHITECTURE.md` |
| API contract + data shapes | `docs/SPEC.md` |
| Test conventions | `docs/TESTING.md` |
| Raw memory snapshot (frozen) | `docs/memory-snapshot/README.md` |

## Key principles

- **Faithful extraction** — TNA cell content is the source of truth. Copy verbatim; never split, concatenate, or reformat. Fields you can't find are null; add a Warning. See `docs/PRINCIPLES.md`.
- **Route on structural signals, never format/supplier names** — `if format == "DKN"` is a hard anti-pattern. Route on shape (`scattered_kv`, `multi_row_headers`, `vertical_merge_in_data`, etc.).
- **Induction-then-apply** — LLM induces a `SheetPlan` from a small sample; deterministic `apply_plan` iterates all rows. LLM cost is bounded by sheet count, not row count.
- **LLM as reviewer, not producer** — `PlanReviewer` fires only when det validators warn or confidence is low. Det wins on disagreement; LLM call failure is non-blocking.
- **Keep code lean** — when iterating on a layout, sharpen the agent prompt first. Add Python helpers only when prompt + evidence demonstrably can't solve it.
- **Tests are organised by tier** — `unit / flow / agent / e2e / live`. See `docs/TESTING.md`. FakeLLM stubs all LLM calls below the `live` tier.
- **Four extensibility axes** — new layouts add signals (A), schema literals (B), specialist agents (C), or tools (D). Most are A + B; avoid A-inflation. See `docs/PRINCIPLES.md`.
- **Update docs after impl** — README / ARCHITECTURE / SPEC / design docs are updated as the last step, after tests + evals are green.

## Don't do this

- **Don't reference plan-task names in code** — `# SRP Task 17` or `# MA Task 12` in comments/docstrings is a defect. Describe what the code does; task history lives in `docs/superpowers/plans/`.
- **Don't pin to deadlines** — architecture quality over sprint dates. The original M0–M3 milestone dates are soft/historical.
- **Don't split cells** — no splitting one cell across multiple fields, no concatenating multiple cells into one field.
- **Don't add backwards-compatibility hacks for unused code** — delete rather than guard.
- **Don't bypass the fixture pattern in tests** — never call `register_workbook()` directly in a fixture-using test; use `@fixture_case`.

## Working agreements

- **Python version**: 3.12.
- **Venv**: `.venv/` at repo root. Activate per your platform before running anything. Deps in `pyproject.toml`; lock via `pip freeze > requirements.txt` after adding a dep.
- **Full stack**: `make up` — starts `api` + SigNoz stack (ClickHouse, otel-collector, signoz binary). SigNoz UI at `localhost:8080`.
- **Tests (non-live)**: `make test` or `pytest tests -q -m "not live"`. Must pass before any commit.
- **Live tests** (real Anthropic API + real xlsx): `pytest tests -m live -q`. Requires `ANTHROPIC_API_KEY` in `.env`.
- **Eval**: `make eval` — scores extraction against `dataset/extracted/*.json` labels.
- **Labels schema**: `dataset/extracted/*.json`. Canonical field names: `quantity` (not `order_quantity`), nested `source` under each PLI/Stage value.
- **Observability**: all three signals (traces, metrics, logs) flow via OTel SDK → OTLP → otel-collector → ClickHouse → SigNoz UI. No Prometheus scrape endpoint; no `/metrics` route.
- **Commit style**: conventional commits (`feat/fix/chore/docs/test/refactor`). No task-name references in commit bodies.
