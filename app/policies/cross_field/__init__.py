"""Cross-field policies — operate on the global plan scoreboard.

Each policy reads `dict[canonical → list[(LocationCandidate, score, eliminated)]]`
and emits a list of `PolicyVerdict`s (audit trail) plus a list of
`ValidationWarning`s (carried on the plan / surfaced in `ExtractionResult`).

Future versions of these policies will also mutate scoreboard entries
(boost a runner-up, knock down a conflicting candidate). The current
two policies are validation-style — they emit warnings + verdicts
without modifying scores.
"""
