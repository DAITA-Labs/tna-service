"""P1 probe — shape-inspection tools + multi-vote sheet classification.

Layout (read top-to-bottom):
    shape_models.py — Pydantic models for ShapeSummary, Rect, BlankRun,
                      HeaderCandidate, ColumnDtypeProfile, etc.
    shape_tools.py  — all shape tools (with A/B/C variants where applicable).
    checks.py       — classification checks + multi-vote aggregator.
    run_p1.py       — harness: loads files, runs tools+checks, emits the
                      markdown report next to this package.

Nothing inside experiments/specs/ is modified — we only import from it.
"""
