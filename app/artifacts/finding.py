"""Finding / Verdict / ValidationWarning — extraction-result vocabulary.

Findings are the unit of currency between field components, validators,
and judges. A Finding carries the extracted value, its source coordinates,
a confidence level, and a list of evidence tags. Verdicts are LLM judge
outputs over Findings. ValidationWarnings are structural-query validator
outputs flagging constraint violations.

These records carry coordinates as `(column_letter, row_index_1based)`
tuples — the same format every spec uses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


Coord = tuple[str, int]


class Confidence(str, Enum):
    """Three-level confidence ladder used by every Finding and Verdict."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Finding:
    """One extracted field value with its source coordinates and evidence trail.

    Findings flow from per-canonical components to validators to judges to
    the Reconciler. Coordinates point into the canvas; the value is the
    extracted content. Evidence carries structural facts that supported
    this finding (e.g. HEADER_BAND_MEMBER, SAME_LENGTH_STRIP, DTYPE_MATCH).
    """

    canonical:      str
    label_coord:    Coord
    value_coord:    Coord
    value:          Any
    confidence:     Confidence
    evidence:       list[str] = field(default_factory=list)
    decision_notes: str | None = None


@dataclass
class Verdict:
    """LLM judge output for one ambiguous Finding.

    `keep` accepts the finding; `drop` excludes it from the final PLI;
    `rewrite` replaces it with a new finding at `alternative_coord`.
    """

    decision:          Literal["keep", "drop", "rewrite"]
    reason:            str
    alternative_coord: Coord | None = None
    confidence:        Confidence = Confidence.MEDIUM


@dataclass
class ValidationWarning:
    """Structural-query validator output flagging a constraint violation.

    Severities follow standard log levels: 'info' for advisory signals
    (e.g. repeating-header pattern detected), 'warning' for likely issues
    (e.g. orphan dates), 'error' for hard contract violations (e.g.
    mandatory io_number missing on a PLI row).
    """

    name:             str
    severity:         Literal["info", "warning", "error"]
    message:          str
    affects_findings: list[Finding] = field(default_factory=list)

    def affects(self, finding: Finding) -> bool:
        """Return True if this warning was raised against `finding`."""
        return finding in self.affects_findings
