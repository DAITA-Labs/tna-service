"""Single-import-path coverage for app/enums/."""
from __future__ import annotations


def test_field_scope_reexported() -> None:
    from app.enums import FieldScope as Reexp
    from app.specs.enums import FieldScope as Canonical

    assert Reexp is Canonical


def test_value_dtype_reexported() -> None:
    from app.enums import ValueDtype as Reexp
    from app.specs.enums import ValueDtype as Canonical

    assert Reexp is Canonical


def test_value_dtype_mode_reexported() -> None:
    from app.enums import ValueDtypeMode as Reexp
    from app.specs.enums import ValueDtypeMode as Canonical

    assert Reexp is Canonical


def test_label_match_mode_reexported() -> None:
    from app.enums import LabelMatchMode as Reexp
    from app.specs.enums import LabelMatchMode as Canonical

    assert Reexp is Canonical


def test_new_enums_reexported_from_package() -> None:
    """Every new enum from Phase 1 is reachable via `from app.enums import …`."""
    from app.enums import (
        ClusterRole,
        FieldLocationMode,
        JudgeDecision,
        PliAxis,
        PolicySeverity,
        StageAxis,
        SubfieldAxis,
    )

    assert FieldLocationMode.COLUMN.value == "column"
    assert StageAxis.HORIZONTAL.value     == "horizontal"
    assert SubfieldAxis.IMPLICIT.value    == "implicit"
    assert JudgeDecision.APPROVE.value    == "approve"
    assert PolicySeverity.WARNING.value   == "warning"
    assert ClusterRole.PLI_CLUSTER.value  == "pli_cluster"
    assert PliAxis.ROW.value              == "row"


def test_existing_enums_still_reexported() -> None:
    """The pre-existing app/enums/ classes remain reachable from the package."""
    from app.enums import (
        CellDtype,
        Environment,
        LocationPattern,
        PliMode,
        RowRole,
        StageScope,
        SubRowRole,
        ValidationSeverity,
    )

    # Smoke check: each is an Enum subclass with at least one member.
    for cls in (CellDtype, Environment, LocationPattern, PliMode,
                RowRole, StageScope, SubRowRole, ValidationSeverity):
        assert hasattr(cls, "__members__")
        assert len(cls.__members__) > 0
