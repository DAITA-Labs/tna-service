"""Sub-field specs — the canonical sub-column types inside a stage band.

Small canonical set (~6-9). The empirical experiment showed this is the
most deterministic-friendly sub-problem (vocab alone reached F1=1.0).

In the proposed simplified Stage model, only `planned_date` is first-class
(it becomes `Stage.plan_date`). The others get folded into
`Stage.stage_metadata{k:v}`. Specs are still kept here because:
  - the matcher uses them to NAME the sub-columns
  - the judge prompts read description/patterns/anti-patterns for context
"""
from __future__ import annotations

from app.specs._base import SubfieldSpec
from app.specs.enums import LabelMatchMode, ValueDtype


PLANNED_DATE_SPEC = SubfieldSpec(
    canonical="planned_date",
    description=(
        "The planned/scheduled date for the parent stage. First-class on a "
        "Stage object — becomes Stage.plan_date."
    ),
    aliases=("plan", "plan date", "planned", "pln", "scheduled"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.DATE,
    patterns=("labels like 'PLAN', 'Planned', 'Plan Date'",),
    anti_patterns=(
        "do NOT match 'ACT' or 'Actual' — those are actual_date",
    ),
    examples=("PLAN", "Planned", "Plan Date", "PLN"),
)


ACTUAL_DATE_SPEC = SubfieldSpec(
    canonical="actual_date",
    description="The actual date the stage finished (vs the planned date).",
    aliases=("act", "actual", "actual date", "done", "completed", "ach"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.DATE,
    patterns=("labels like 'ACT', 'Actual', 'Done'",),
    anti_patterns=("do NOT match 'PLAN' / 'Planned' — those are planned_date",),
    examples=("ACT", "Actual", "Done", "Completed"),
)


APPROVAL_DATE_SPEC = SubfieldSpec(
    canonical="approval_date",
    description="Date the stage was approved (e.g. fit_approval, sample_approval).",
    aliases=("appd", "approved", "approval", "app", "approval date"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.DATE,
    patterns=("labels like 'APPD', 'Approved', 'Approval'",),
    anti_patterns=("do NOT match 'PLAN' — that is planned_date",),
    examples=("APPD", "Approved", "Approval"),
)


RECEIVED_DATE_SPEC = SubfieldSpec(
    canonical="received_date",
    description="Date materials were received (e.g. fabric received).",
    aliases=("recvd", "received", "rcvd", "rec", "rcd", "received date"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.DATE,
    patterns=("labels like 'RECVD', 'Received'",),
    anti_patterns=(),
    examples=("RECVD", "Received", "RCVD"),
)


START_DATE_SPEC = SubfieldSpec(
    canonical="start_date",
    description="Date stage started (used when stage has both start + end sub-cols).",
    aliases=("start", "start date", "sd", "begin"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.DATE,
    patterns=("labels like 'START', 'Start Date'",),
    anti_patterns=(
        "AMBIGUOUS bare 'START' — could be sewing_start stage rather than start_date sub-field",
    ),
    examples=("START", "Start", "SD"),
)


END_DATE_SPEC = SubfieldSpec(
    canonical="end_date",
    description="Date stage ended.",
    aliases=("end", "end date", "ed", "finish", "complete"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.DATE,
    patterns=("labels like 'END', 'End Date'",),
    anti_patterns=(
        "AMBIGUOUS bare 'END' — could be sewing_end stage",
    ),
    examples=("END", "End", "ED"),
)


APPROVED_QTY_SPEC = SubfieldSpec(
    canonical="approved_qty",
    description="Quantity approved at this stage (e.g. inspection-approved pieces).",
    aliases=("appd qty", "approved qty", "app qty", "qty appd", "qty approved"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.INT,
    patterns=("labels like 'APPD Qty', 'Approved Qty'",),
    anti_patterns=("do NOT match 'Order Qty' — that's the top-level quantity",),
    examples=("APPD Qty", "Approved Qty"),
)


QUANTITY_SUBFIELD_SPEC = SubfieldSpec(
    canonical="quantity",
    description="Quantity associated with the stage (e.g. cut_qty, sewn_qty).",
    aliases=("qty", "quantity", "pcs"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.INT,
    patterns=("labels like 'Qty' inside a stage band",),
    anti_patterns=("do NOT match top-level Order Qty",),
    examples=("Qty", "Pcs"),
)


REMARKS_SPEC = SubfieldSpec(
    canonical="remarks",
    description="Free-text remarks / notes attached to the stage.",
    aliases=("remarks", "notes", "remark", "note", "comments", "comment"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.STR,
    patterns=("labels like 'Remarks', 'Notes'",),
    anti_patterns=(),
    examples=("Remarks", "Notes"),
)


STATUS_SPEC = SubfieldSpec(
    canonical="status",
    description=(
        "Stage progress status — typically a short tag like 'Done', 'In Process', "
        "'Pending', 'Clear', 'Closed'. Carries the operational state of the stage "
        "alongside its planned_date."
    ),
    aliases=("status", "state", "progress", "action", "remark status"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.STR,
    patterns=("labels like 'Status', 'Action', 'Progress'",),
    anti_patterns=(
        "do NOT match 'Status Date' — that's actual_date or approval_date",
    ),
    examples=("Status", "Action", "Progress"),
)


# =============================================================================
# Registry — every sub-field spec
# =============================================================================

SUBFIELD_SPECS: tuple[SubfieldSpec, ...] = (
    PLANNED_DATE_SPEC,
    ACTUAL_DATE_SPEC,
    APPROVAL_DATE_SPEC,
    RECEIVED_DATE_SPEC,
    START_DATE_SPEC,
    END_DATE_SPEC,
    APPROVED_QTY_SPEC,
    QUANTITY_SUBFIELD_SPEC,
    REMARKS_SPEC,
    STATUS_SPEC,
)

SUBFIELD_CANONICALS: tuple[str, ...] = tuple(s.canonical for s in SUBFIELD_SPECS)


def get_subfield_spec(canonical: str) -> SubfieldSpec:
    for spec in SUBFIELD_SPECS:
        if spec.canonical == canonical:
            return spec
    raise KeyError(f"unknown subfield canonical: {canonical!r}")
