"""app.enums — single import path for the project's enums.

New code MUST import every enum from this package. Legacy modules
(`app/specs/enums.py`) keep working via re-exports below — see spec
§4 of the plan-driven canvas architecture.
"""
from __future__ import annotations

# Phase 1 (plan-driven canvas arch) new enums.
from app.enums.field_location_mode import FieldLocationMode
from app.enums.field_scope         import FieldScope
from app.enums.judge_decision      import JudgeDecision
from app.enums.pli_axis            import PliAxis
from app.enums.policy_severity     import PolicySeverity
from app.enums.read_direction      import ReadDirection
from app.enums.stage_axis          import StageAxis
from app.enums.subfield_axis       import SubfieldAxis

# Pre-existing enums already housed in app/enums/.
from app.enums.cell_dtype          import CellDtype
from app.enums.environment         import Environment
from app.enums.location_pattern    import LocationPattern
from app.enums.pli_mode            import PliMode
from app.enums.row_role            import RowRole, SubRowRole
from app.enums.stage_scope         import StageScope
from app.enums.validation_severity import ValidationSeverity

# Legacy enums still defined in app/specs/enums.py — re-export here for
# a single import path. Existing imports from app.specs.enums keep working.
from app.specs.enums import (
    LabelMatchMode,
    ValueDtype,
    ValueDtypeMode,
)

__all__ = [
    # Phase-1 new
    "FieldLocationMode",
    "FieldScope",
    "JudgeDecision",
    "PliAxis",
    "PolicySeverity",
    "ReadDirection",
    "StageAxis",
    "SubfieldAxis",
    # Pre-existing app/enums/
    "CellDtype",
    "Environment",
    "LocationPattern",
    "PliMode",
    "RowRole",
    "StageScope",
    "SubRowRole",
    "ValidationSeverity",
    # Legacy specs/enums re-exports
    "LabelMatchMode",
    "ValueDtype",
    "ValueDtypeMode",
]
