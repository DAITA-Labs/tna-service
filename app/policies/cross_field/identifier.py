"""Cross-field identifier policies — global checks across canonicals.

Each policy reads the global scoreboard
(`dict[str, list[tuple[LocationCandidate, float, bool]]]`) and returns
`(verdicts, warnings)`:

  - `verdicts` — `PolicyVerdict`s targeting `"<plan>"` (or `"<plan:canonical>"`)
    that record the policy's audit reasoning.
  - `warnings` — `ValidationWarning`s the plan carries forward into
    `ExtractionResult.warnings`.

Policies do NOT mutate the scoreboard today; they're validation-style.
A future iteration may add boost / penalize / eliminate side effects.
"""
from __future__ import annotations

from typing import Any

from app.artifacts.finding import ValidationWarning
from app.artifacts.plan import LocationCandidate
from app.policies._base import PolicyVerdict


_DATE_TRIO = ("ex_fty_date", "shipment_date", "delivery_date")
_DEFAULT_SCORE_FLOOR = 0.5
_PLAN_CANDIDATE = "<plan>"


# Type alias — the scoreboard shape every cross-field policy reads.
ScoreBoard = dict[str, list[tuple[LocationCandidate, float, bool]]]


def at_least_one_date_trio_member_present(
    scoreboard:  ScoreBoard,
    *,
    score_floor: float = _DEFAULT_SCORE_FLOOR,
    **_:         Any,
) -> tuple[list[PolicyVerdict], list[ValidationWarning]]:
    """Require ≥1 of {ex_fty, shipment, delivery}_date to be located.

    Zero located → severe penalty verdict + error-level warning.
    """
    best_scores: dict[str, float] = {}
    located_count = 0
    for canonical in _DATE_TRIO:
        cands     = scoreboard.get(canonical, [])
        survivors = [(c, s) for c, s, elim in cands if not elim]
        if not survivors:
            best_scores[canonical] = 0.0
            continue
        best                       = max(survivors, key=lambda pair: pair[1])
        best_scores[canonical]     = best[1]
        if best[1] >= score_floor:
            located_count += 1

    verdict = PolicyVerdict(
        name="at_least_one_date_trio_member_present",
        candidate=_PLAN_CANDIDATE,
        score_delta=0.0 if located_count >= 1 else -1.0,
        message=f"located={located_count} scores={best_scores}",
    )
    warnings: list[ValidationWarning] = []
    if located_count == 0:
        warnings.append(ValidationWarning(
            name="date_trio_all_missing",
            severity="error",
            message=(
                "No member of (ex_fty_date, shipment_date, delivery_date) "
                f"scored above {score_floor}. Best scores: {best_scores}"
            ),
        ))
    return [verdict], warnings


def mandatory_canonicals_must_be_located(
    scoreboard:  ScoreBoard,
    *,
    mandatory:   tuple[str, ...] = ("io_number", "quantity"),
    score_floor: float           = _DEFAULT_SCORE_FLOOR,
    **_:         Any,
) -> tuple[list[PolicyVerdict], list[ValidationWarning]]:
    """Every mandatory canonical must have a candidate above the floor.

    No candidates  → error-level warning, -1.0 verdict.
    Below floor    → warning-level warning, -0.5 verdict.
    Above floor    → no warning, 0.0 verdict.
    """
    verdicts: list[PolicyVerdict]      = []
    warnings: list[ValidationWarning]  = []

    for canonical in mandatory:
        cands     = scoreboard.get(canonical, [])
        survivors = [(c, s) for c, s, elim in cands if not elim]

        if not survivors:
            verdicts.append(PolicyVerdict(
                name="mandatory_canonicals_must_be_located",
                candidate=f"<plan:{canonical}>",
                score_delta=-1.0,
                message=f"{canonical} has no candidates",
            ))
            warnings.append(ValidationWarning(
                name=f"mandatory_missing_{canonical}",
                severity="error",
                message=f"Mandatory canonical {canonical!r} has no candidates",
            ))
            continue

        best_score = max(s for _, s in survivors)
        if best_score < score_floor:
            verdicts.append(PolicyVerdict(
                name="mandatory_canonicals_must_be_located",
                candidate=f"<plan:{canonical}>",
                score_delta=-0.5,
                message=f"{canonical} best score {best_score:.2f} below floor {score_floor}",
            ))
            warnings.append(ValidationWarning(
                name=f"mandatory_low_confidence_{canonical}",
                severity="warning",
                message=(
                    f"Mandatory canonical {canonical!r}'s best score "
                    f"{best_score:.2f} is below the floor {score_floor}"
                ),
            ))
        else:
            verdicts.append(PolicyVerdict(
                name="mandatory_canonicals_must_be_located",
                candidate=f"<plan:{canonical}>",
                score_delta=0.0,
                message=f"{canonical} located at {best_score:.2f}",
            ))

    return verdicts, warnings
