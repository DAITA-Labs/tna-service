"""Spec dataclasses — single source of truth per canonical field.

A spec drives BOTH:
  - the deterministic matcher (find_field_locations + dtype/constraint filter)
  - the LLM judge prompt (patterns, anti-patterns, description shown to judge)

Update the spec in one place → both layers see the change.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.specs.enums import (
    Area,
    LabelMatchMode,
    ValueDtype,
    ValueDtypeMode,
    ValuePattern,
)


# =============================================================================
# Constraint sub-types
# =============================================================================


@dataclass(frozen=True)
class ValueConstraints:
    """Range / length / regex constraints on the value cell.

    Used by the deterministic matcher to filter candidates AND by the judge
    prompt to know what 'valid' looks like for this field.
    """
    min:                float | None                 = None
    max:                float | None                 = None
    min_len:            int | None                   = None
    max_len:            int | None                   = None
    regex:              str | None                   = None
    allowed_patterns:   tuple[ValuePattern, ...]     = ()


# =============================================================================
# FieldSpec — for IDENTIFIERS area (and METADATA area extensions)
# =============================================================================


@dataclass(frozen=True)
class FieldSpec:
    """Complete spec for one canonical identifier/metadata field.

    Reads (deterministic matcher):
        canonical          → output canonical name
        aliases            → vocab table entries
        label_match_mode   → fuzzy/jaccard thresholds
        value_dtype        → expected adjacent-value dtype
        value_dtype_mode   → how strict the dtype filter is
        value_constraints  → range/length/pattern checks

    Renders into judge prompts:
        description        → "what is this field?"
        patterns           → positive examples (LOOKS like)
        anti_patterns      → negative examples (DO NOT match)
        examples           → real raw labels seen in the wild

    Pipeline properties:
        area               → which top-level area
        mandatory          → must this field appear in every PLI?
    """
    # Identity
    canonical:         str
    area:              Area
    description:       str

    # Deterministic matching
    aliases:           tuple[str, ...]
    label_match_mode:  LabelMatchMode             = LabelMatchMode.MEDIUM
    value_dtype:       ValueDtype                  = ValueDtype.ANY
    value_dtype_mode:  ValueDtypeMode              = ValueDtypeMode.MEDIUM
    value_constraints: ValueConstraints            = field(default_factory=ValueConstraints)

    # Prompt rendering
    patterns:          tuple[str, ...]             = ()
    anti_patterns:     tuple[str, ...]             = ()
    examples:          tuple[str, ...]             = ()

    # Pipeline properties
    mandatory:         bool                        = False


# =============================================================================
# StageSpec — for STAGES area (canonical stage names)
# =============================================================================


@dataclass(frozen=True)
class StageSpec:
    """Spec for a canonical stage name.

    Stages have an implicit value_dtype = DATE for the plan_date column,
    so we don't expose dtype configuration here. The other fields play
    the same roles as FieldSpec.
    """
    canonical:         str
    description:       str
    aliases:           tuple[str, ...]
    label_match_mode:  LabelMatchMode             = LabelMatchMode.MEDIUM

    patterns:          tuple[str, ...]             = ()
    anti_patterns:     tuple[str, ...]             = ()
    examples:          tuple[str, ...]             = ()

    # Typical position hint — does this stage usually come early/middle/late
    # in the sequence? Used as a tiebreaker by some classification checks.
    sequence_hint:     str                          = ""    # "early" | "middle" | "late" | ""


# =============================================================================
# SubfieldSpec — for sub-columns inside a stage band (PLAN/ACT/RECVD/APPD)
# =============================================================================


@dataclass(frozen=True)
class SubfieldSpec:
    """Spec for a canonical stage sub-field (the column WITHIN a stage band).

    Small canonical set (~6-9), low ambiguity. Often deterministic-only.
    """
    canonical:         str
    description:       str
    aliases:           tuple[str, ...]
    label_match_mode:  LabelMatchMode             = LabelMatchMode.MEDIUM

    # Sub-fields tend to have a strong value-dtype expectation
    value_dtype:       ValueDtype                  = ValueDtype.ANY

    patterns:          tuple[str, ...]             = ()
    anti_patterns:     tuple[str, ...]             = ()
    examples:          tuple[str, ...]             = ()
