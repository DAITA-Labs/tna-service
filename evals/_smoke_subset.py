"""Smoke subset of the eval corpus — 7 representative files for fast iteration.

The full eval corpus has 23 labeled files and takes ~5-10 minutes of real
Anthropic API calls. This subset trades coverage for speed: ~7 files cover
the main layout families and the previously-broken-now-fixed cases, so a
single `make eval-smoke` run validates that an extractor or scorer change
has not regressed the load-bearing cases.

Selected for diversity:
  - ROW_PER_PLI with vertical merges        — CHRISTIAN BERG
  - ROW_PER_PLI columnar (multi-row header) — DKN AW26 WOMEN NOS
  - ROW_PER_PLI columnar (Compass Pro)      — MOP MANOS07-08
  - ROW_PER_PLI flat with TOTAL footers     — FA26 YC & EUROPE
  - ROW_PER_PLI with sheet title row        — NORTHERN REFLECTIONS
  - SHEET_IS_PLI Orders Plan (tall_sub_rows)— 63261-TNA
  - SHEET_IS_PLI Orders Plan (multi-sheet)  — new job-TNA

For the full corpus, run `make eval` (no flag).
"""
from __future__ import annotations

SMOKE_SUBSET: frozenset[str] = frozenset({
    "CHRISTIAN BERG- T&A",
    "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS",
    "20260420 MOP W26(1) MANOS07-08 COMPASS PRO",
    "FA26 YC & EUROPE T&A #1",
    "63261-TNA",
    "new job-TNA",
    "NORTHERN REFLECTIONS- T&a",
})
