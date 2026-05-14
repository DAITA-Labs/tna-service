# docs/memory-snapshot — README

## What this directory is

A frozen snapshot of Claude Code's per-project auto-memory as it existed on 2026-05-14, taken immediately before the primary development machine migrated from Windows to macOS. It contains 19 `.md` files that were the live auto-memory for this project.

## Why it exists alongside CLAUDE.md / PRINCIPLES.md / ADRs

Claude Code's auto-memory (`~/.claude/projects/<slug>/memory/`) is machine-local and session-volatile. The files here are the *raw* opinionated layer: informal, first-person, sometimes redundant, always tied to a specific session. They were the source for the curated promotions:

| Raw file here | Promoted to |
|---|---|
| `faithful_extraction_principle.md` | `docs/PRINCIPLES.md` §1 + `docs/adrs/0002-faithful-extraction.md` |
| `feedback_routing_principle.md` | `docs/PRINCIPLES.md` §2 + `docs/adrs/0001-multi-agent-split.md` |
| `extensibility_axes.md` | `docs/PRINCIPLES.md` §5 + `docs/adrs/0003-sheet-row-planner.md` |
| `feedback_code_style.md` | `docs/PRINCIPLES.md` §6 |
| `feedback_no_task_refs_in_code.md` | `docs/PRINCIPLES.md` §7 + `CLAUDE.md` "Don't do this" |
| `feedback_keep_code_lean.md` | `docs/PRINCIPLES.md` §6 + `CLAUDE.md` |
| `feedback_no_deadline_experiment_first.md` | `docs/PRINCIPLES.md` §9 + `CLAUDE.md` |
| `feedback_update_docs_after_impl.md` | `docs/PRINCIPLES.md` §8 |
| `llm_as_judge_pattern.md` | `docs/PRINCIPLES.md` §4 + `docs/adrs/0003-sheet-row-planner.md` |
| `architecture_decision.md` | `docs/adrs/0001`, `0003` |
| `m0_baseline_results.md` | `docs/JOURNEY.md` Phase 1 |
| `m0_implementation_complete.md` | `docs/JOURNEY.md` Phase 1 |
| `dataset_observations.md` | `docs/JOURNEY.md` Phase 0 |
| `signoz_migration_model.md` | `docs/adrs/0005-signoz-migration.md` |

The curated docs are the live source of truth. This directory is **frozen**. Don't update these files — update `CLAUDE.md`, `docs/PRINCIPLES.md`, `docs/adrs/`, `ARCHITECTURE.md`, or `docs/SPEC.md` instead.

## How to re-hydrate auto-memory on a new machine

Claude Code stores per-project auto-memory under `~/.claude/projects/<slug>/memory/`, where `<slug>` is derived from the absolute path of the repo on the current machine.

Steps:
1. Open Claude Code in this repo at least once to trigger the creation of the project memory directory.
2. Run `ls ~/.claude/projects/` to find the slug that matches this repo's absolute path (e.g., `-Users-nagasai-dev-tna-service` for a clone at `/Users/nagasai/dev/tna-service`).
3. Copy the files from this directory into `~/.claude/projects/<slug>/memory/`:
   ```
   cp docs/memory-snapshot/*.md ~/.claude/projects/<slug>/memory/
   ```
4. Claude Code will pick them up on the next session start.

Note: the slug format is the absolute path with `/` and spaces replaced by `-`. It is machine-specific — the slug on macOS for `/Users/nagasai/dev/tna-service` differs from the Windows slug for `F:\DAITA\ARENA\TNA\tna-service`.
