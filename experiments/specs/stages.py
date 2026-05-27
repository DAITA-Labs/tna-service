"""Stage specs — ADVISORY HINTS for known common stages.

OPEN VOCABULARY DESIGN
======================
Stages are an OPEN set. Any TNA can have any stage names — supplier-specific,
new processes, locale-specific terms. The detector must NOT require a match
against STAGE_SPECS to emit a stage.

HARD PRINCIPLE: ONE PLANNED_DATE ⇒ ONE STAGE
============================================
Every distinct (label, planned_date_column) pair in the sheet is its OWN
stage. Names that LOOK like one concept but have separate planned_date
columns must NOT be collapsed:

  ✓ CORRECT (two stages):
      Stage(name="Sewing Start", plan_date_col=Z, plan_date="2026-05-23")
      Stage(name="Sewing End",   plan_date_col=AB, plan_date="2026-06-05")

  ✗ WRONG (collapsed — loses precision):
      Stage(name="Sewing", plan_date_col=Z, plan_date="2026-05-23")
      # Sewing End's separate planned_date silently dropped

Same applies to: PP Send vs PP Approval, Fit Send vs Fit Approval,
Cutting Plan vs Cutting Start, Fabric Inhouse Send vs Fabric Inhouse
Approval, etc. Each is a separate stage with its own canonical name (or
verbatim name if unknown) and its own planned_date.

The non-planned date sub-columns (actual, received, approved, qty,
remarks) STILL fold into the stage's `stage_metadata` bag — they are
attached to the SAME stage as the planned_date, not split off.

How STAGE_SPECS is actually used:

1. DETECTION SIGNAL — known stage aliases in a header row strengthen
   "this column is a stage band" confidence; they DO NOT gate emission.
   A column under a header cell whose text is `"BULK PACKING"` (unknown
   to STAGE_SPECS) is still emitted as a stage if it has date-bearing data
   below.

2. ANTI-PATTERN GUARDS — patterns/anti_patterns help avoid false positives
   (e.g. "Fabric #" header column should NOT be detected as a fabric stage).

3. SEQUENCE VALIDATION — sequence_hint (early/middle/late) helps the phase
   judge validate that detected stages appear in a plausible chronological
   order. Optional; doesn't block emission.

4. OPTIONAL CANONICALIZATION — if the supplier's raw text fuzzy-matches a
   known StageSpec alias, the emitted Stage gets `canonical = <known name>`.
   If no match, `canonical = None` and `name = <raw text as written>`.

A Stage shipped downstream:

    Stage(
        name="BULK PACKING",            # verbatim from sheet
        canonical=None,                 # not in our hint table
        plan_date="2026-04-15",
        plan_date_col=14,
        column_range=(14, 15),
        stage_metadata={"actual_date": "2026-04-14", "remarks": "..."},
    )

vs

    Stage(
        name="SEWING",
        canonical="sewing",             # matched a known StageSpec
        plan_date="2026-03-05",
        ...
    )

To add a NEW known stage to the hint table:
  1. Append a new StageSpec below
  2. Add to STAGE_SPECS at the bottom of the file
  3. Optional — but the system will work without it
"""
from __future__ import annotations

from ._base import StageSpec
from .enums import LabelMatchMode


# =============================================================================
# Fabric stages
# =============================================================================

FABRIC_SPEC = StageSpec(
    canonical="fabric",
    description=(
        "Fabric-related stage. Often the first stage chronologically. May "
        "appear as a single band or split into fabric_send / in_house_fabric_send."
    ),
    aliases=(
        "fabric", "fab", "fabric plan", "fab plan", "fabric eta plan",
        "fabric inhouse", "fab inhouse", "in-house fabric",
    ),
    patterns=(
        "labels like 'Fabric', 'Fab', 'FAB PLAN', 'Fabric Inhouse'",
        "stage appears chronologically EARLY in a TNA",
    ),
    anti_patterns=(
        "do NOT match 'Fabric #' or 'Fabric Code' — those are identifier fields",
        "do NOT match 'Fabric Quality' label — that is fabric_name (identifier)",
    ),
    examples=("FABRIC", "FAB", "FAB PLAN", "Fabric Inhouse"),
    sequence_hint="early",
)


IN_HOUSE_FABRIC_SEND_SPEC = StageSpec(
    canonical="in_house_fabric_send",
    description=(
        "Date fabric was sent to in-house warehouse. Distinct from "
        "in_house_fabric_approval (date fabric was approved on receipt)."
    ),
    aliases=(
        "fabric in-house", "fab in-house", "fabric inhouse send",
        "in-house fabric send", "fabric in house",
    ),
    patterns=(
        "labels mentioning 'In-House' or 'Inhouse' together with 'Send' or 'Sent'",
    ),
    anti_patterns=(
        "do NOT match 'IN-HOUSED ON' (that's an approval/receipt date — separate stage)",
    ),
    examples=("Fabric In-House", "Fabric Inhouse Send"),
    sequence_hint="early",
)


# =============================================================================
# Pre-production stages
# =============================================================================

PRE_PRODUCTION_SEND_SPEC = StageSpec(
    canonical="pre_production_send",
    description="Date the pre-production (PP) sample was sent to the buyer.",
    aliases=(
        "pp send", "pp sent", "pp submit", "pp submission",
        "pre-production send", "pre production send", "pps",
        "program submit on",
    ),
    patterns=("labels containing 'PP' alongside 'send' or 'submit'",),
    anti_patterns=("do NOT match 'PP Approval' — that is pp_approval",),
    examples=("PP Send", "PP Sent", "PP Submission"),
    sequence_hint="early",
)


SIZESET_SUBMISSION_SPEC = StageSpec(
    canonical="sizeset_submission",
    description="Date size-set samples were submitted to buyer for approval.",
    aliases=(
        "size set", "sizeset", "ss", "size set submission",
        "sizeset submission", "ss submission",
    ),
    patterns=("labels like 'Size Set', 'SS Submission'",),
    anti_patterns=("do NOT match 'Size Set Approval'",),
    examples=("Size Set", "Sizeset Submission", "SS"),
    sequence_hint="middle",
)


# =============================================================================
# Production stages
# =============================================================================

CUTTING_SPEC = StageSpec(
    canonical="cutting",
    description="Cutting stage (panels cut from fabric).",
    aliases=(
        "cutting", "cut", "cutting plan", "cutting start", "cut start",
    ),
    patterns=("labels like 'CUTTING', 'CUT', 'Cutting Plan'",),
    anti_patterns=(
        "do NOT match 'Cut Qty' — that's quantity inside stage_metadata",
    ),
    examples=("CUTTING", "Cutting Plan", "CUT"),
    sequence_hint="middle",
)


SEWING_SPEC = StageSpec(
    canonical="sewing",
    description="Sewing/stitching stage.",
    aliases=(
        "sewing", "sew", "stitching", "sewing plan",
    ),
    patterns=("labels like 'SEWING', 'SEW', 'Stitching'",),
    anti_patterns=(
        "do NOT match 'Sewing Start' or 'Sewing End' — those are separate stages",
    ),
    examples=("SEWING", "Sewing Plan", "Stitching"),
    sequence_hint="middle",
)


SEWING_START_SPEC = StageSpec(
    canonical="sewing_start",
    description="Date sewing started.",
    aliases=(
        "sewing start", "sew start", "stitching start", "sewing start plan",
        "start", "start sewing",
    ),
    patterns=("labels like 'Sewing Start', 'Start'",),
    anti_patterns=(
        "do NOT match bare 'START' if context lacks sewing — escalate to phase judge",
    ),
    examples=("Sewing Start", "Start", "Start Sewing"),
    sequence_hint="middle",
)


SEWING_END_SPEC = StageSpec(
    canonical="sewing_end",
    description="Date sewing finished.",
    aliases=(
        "sewing end", "sew end", "stitching end", "sewing end plan",
        "end", "end sewing",
    ),
    patterns=("labels like 'Sewing End', 'End'",),
    anti_patterns=(
        "do NOT match bare 'END' if context lacks sewing — escalate to phase judge",
    ),
    examples=("Sewing End", "End", "End Sewing"),
    sequence_hint="middle",
)


# =============================================================================
# Approval / finishing stages
# =============================================================================

FIT_SEND_SPEC = StageSpec(
    canonical="fit_send",
    description="Date the fit sample was sent to buyer.",
    aliases=("fit send", "fit sent", "fit sample send",),
    patterns=("labels like 'Fit Send', 'Fit Sample Sent'",),
    anti_patterns=("do NOT match 'Fit Approval'",),
    examples=("Fit Send", "Fit Sample Sent"),
    sequence_hint="middle",
)


FIT_APPROVAL_SPEC = StageSpec(
    canonical="fit_approval",
    description="Date the fit sample was approved by buyer.",
    aliases=(
        "fit approval", "fit approved", "fit appd", "fit ok",
    ),
    patterns=("labels like 'Fit Approval', 'Fit Approved'",),
    anti_patterns=("do NOT match 'Fit Send'",),
    examples=("Fit Approval", "Fit Approved"),
    sequence_hint="middle",
)


FINAL_INSPECTION_SPEC = StageSpec(
    canonical="final_inspection",
    description="Final inspection stage (FI) before shipment.",
    aliases=(
        "fi", "final inspection", "final-inspection", "final inspect",
        "inspection",
    ),
    patterns=("labels like 'FI', 'Final Inspection'",),
    anti_patterns=(),
    examples=("FI", "Final Inspection", "Inspection"),
    sequence_hint="late",
)


EX_FACTORY_SHIPMENT_SPEC = StageSpec(
    canonical="ex_factory_shipment",
    description="Ex-factory shipment date — when goods left the factory.",
    aliases=(
        "ex factory", "ex-factory", "exf", "shipment", "ex factory shipment",
        "ship", "shipping",
    ),
    patterns=("labels like 'Ex Factory', 'Shipment', 'Ex-Factory'",),
    anti_patterns=(
        "do NOT match 'Delivery Date' — that's an identifier",
        "do NOT match 'Ex-Factory Date' label at sheet-level — that may be metadata.ex_factory_date",
    ),
    examples=("Ex Factory", "Shipment", "Ex-Factory Shipment"),
    sequence_hint="late",
)


# =============================================================================
# Production / VAP stages
# =============================================================================

VAP_SPEC = StageSpec(
    canonical="vap",
    description=(
        "Value-Added Process — printing, embroidery, wash, dyeing, finishing. "
        "Often shown as a single band when the supplier doesn't break out "
        "individual VAP steps."
    ),
    aliases=("vap", "v.a.p", "value added process", "value-added", "vap plan"),
    patterns=("labels like 'VAP', 'V.A.P', 'VAP PLAN'",),
    anti_patterns=(),
    examples=("VAP", "V.A.P", "VAP PLAN"),
    sequence_hint="middle",
)


LINE_PLAN_SPEC = StageSpec(
    canonical="line_plan",
    description=(
        "Line plan / production-line schedule date. The point at which the "
        "PLI is placed on a sewing line."
    ),
    aliases=("line plan", "line-plan", "line planning", "line plan date", "lp"),
    patterns=("labels like 'Line Plan', 'LP'",),
    anti_patterns=("do NOT match 'Plan' alone — that's a generic plan-marker, not this stage",),
    examples=("Line Plan", "LINE PLAN", "LP"),
    sequence_hint="middle",
)


FEEDING_SPEC = StageSpec(
    canonical="feeding",
    description=(
        "Feeding date — date when cut panels feed into the sewing line. "
        "Comes between cutting and sewing-start."
    ),
    aliases=("feeding", "feed", "feeding plan", "feed plan", "feed start"),
    patterns=("labels like 'Feeding', 'Feed'",),
    anti_patterns=(),
    examples=("Feeding", "FEEDING", "Feed Plan"),
    sequence_hint="middle",
)


# =============================================================================
# Registry — every stage spec
# =============================================================================

STAGE_SPECS: tuple[StageSpec, ...] = (
    FABRIC_SPEC,
    IN_HOUSE_FABRIC_SEND_SPEC,
    PRE_PRODUCTION_SEND_SPEC,
    SIZESET_SUBMISSION_SPEC,
    CUTTING_SPEC,
    SEWING_SPEC,
    SEWING_START_SPEC,
    SEWING_END_SPEC,
    FIT_SEND_SPEC,
    FIT_APPROVAL_SPEC,
    FINAL_INSPECTION_SPEC,
    EX_FACTORY_SHIPMENT_SPEC,
    VAP_SPEC,
    LINE_PLAN_SPEC,
    FEEDING_SPEC,
)

STAGE_CANONICALS: tuple[str, ...] = tuple(s.canonical for s in STAGE_SPECS)


def get_stage_spec(canonical: str) -> StageSpec:
    for spec in STAGE_SPECS:
        if spec.canonical == canonical:
            return spec
    raise KeyError(f"unknown stage canonical: {canonical!r}")
