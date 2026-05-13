"""Synthetic SheetPlan with a CHILD row pointing at a non-existent ANCHOR.

Bypasses the planner — this is corrupt input fed directly into the validator
to confirm Tier 1 catches it.
"""
from app.models.artifacts import SheetPlan, RowSpec
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope


def build_plan() -> SheetPlan:
    return SheetPlan(
        sheet="S",
        pli_mode=PliMode.ROW_PER_PLI,
        identity_column="A",
        header_rows=[1],
        rows=[
            RowSpec(idx=2, role=RowRole.ANCHOR, group_id=0),
            RowSpec(idx=3, role=RowRole.CHILD, anchor_idx=99, group_id=0),
        ],
        stage_scope=StageScope.SHEET_LEVEL,
        confidence=1.0,
    )
