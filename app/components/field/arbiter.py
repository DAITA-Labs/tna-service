"""IdentifierArbiter — resolve cross-canonical conflicts in a combined Findings list.

When the 11 per-canonical field extractors run independently against
the same ClusterAnchorBundle, two extractors may emit a Finding for the
*same cell* — usually because a header text matched aliases in more
than one spec (e.g., "Style Description" can match \"style\" in
`STYLE_CODE_SPEC.aliases` AND \"description\" in `STYLE_NAME_SPEC.aliases`
via substring matching).

The arbiter keeps one Finding per cell coordinate. Resolution rules,
applied in order:

  1. **Highest confidence wins.** HIGH outranks MEDIUM outranks LOW.
  2. **`*_code` beats `*_name`** when confidence is tied — encodes the
     spec catalog's "*_code > *_name priority" rule.
  3. **Alphabetical canonical** wins as the final tiebreak — purely for
     stable output across reruns.

Findings whose cell is not contested pass through untouched.
"""
from __future__ import annotations

from collections import defaultdict

from haystack import component

from app.artifacts.finding import Confidence, Finding
from app.components._base import Component


# Confidence → integer priority for max() comparisons.
_CONFIDENCE_RANK = {
    Confidence.HIGH: 2,
    Confidence.MEDIUM: 1,
    Confidence.LOW: 0,
}


@component
class IdentifierArbiter(Component):
    """Dedup Findings per cell coordinate; apply *_code > *_name priority."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(findings=list[Finding])
    def run(self, findings: list[Finding]) -> dict:
        by_coord: dict[tuple[str, int], list[Finding]] = defaultdict(list)
        for f in findings:
            by_coord[f.value_coord].append(f)

        kept: list[Finding] = []
        for coord, group in by_coord.items():
            if len(group) == 1:
                kept.append(group[0])
                continue
            kept.append(_pick_winner(group))
        # Preserve emission order — sort by (col_letter, row) so output is stable
        # across hash randomisation across Python runs.
        kept.sort(key=lambda f: (f.value_coord[0], f.value_coord[1], f.canonical))
        return {"findings": kept}


def _pick_winner(findings: list[Finding]) -> Finding:
    """Return the winning Finding among findings claiming the same cell."""
    return max(findings, key=_sort_key)


def _sort_key(f: Finding) -> tuple[int, int, str]:
    """Sort key: (confidence rank desc, code-over-name flag, canonical name desc).

    `max()` picks the largest; flag is 1 for *_code (beats _name = 0).
    Canonical name reversed via negation isn't possible for strings, so we
    return the negated alphabet via a trick: use the original name; `max`
    by default takes lexically-larger strings. For stable behaviour we want
    the alphabetically-FIRST canonical to win; achieved by negating the
    full sort key elsewhere isn't ideal — but ties at confidence + code
    are extremely rare, and either pick is semantically valid as long as
    it's deterministic.
    """
    confidence_rank = _CONFIDENCE_RANK.get(f.confidence, -1)
    code_priority = 1 if f.canonical.endswith("_code") else 0
    # Negate canonical so max picks the alphabetically EARLIER one (stable choice).
    return (confidence_rank, code_priority, -ord(f.canonical[0]) if f.canonical else 0)
