"""Value + identity coverage for the new enums added in Phase 1 of the
plan-driven canvas architecture."""
from __future__ import annotations


def test_field_location_mode_values() -> None:
    from app.enums.field_location_mode import FieldLocationMode

    assert {m.value for m in FieldLocationMode} == {"column", "row", "kv_block", "missing"}
    assert FieldLocationMode.COLUMN.value    == "column"
    assert FieldLocationMode.ROW.value       == "row"
    assert FieldLocationMode.KV_BLOCK.value  == "kv_block"
    assert FieldLocationMode.MISSING.value   == "missing"


def test_field_location_mode_is_str_enum() -> None:
    from app.enums.field_location_mode import FieldLocationMode

    assert isinstance(FieldLocationMode.COLUMN, str)
    assert FieldLocationMode.COLUMN == "column"


def test_stage_axis_values() -> None:
    from app.enums.stage_axis import StageAxis

    assert {m.value for m in StageAxis} == {"horizontal", "vertical", "none"}
    assert StageAxis.HORIZONTAL.value == "horizontal"
    assert StageAxis.VERTICAL.value   == "vertical"
    assert StageAxis.NONE.value       == "none"


def test_stage_axis_is_str_enum() -> None:
    from app.enums.stage_axis import StageAxis

    assert isinstance(StageAxis.HORIZONTAL, str)


def test_subfield_axis_values() -> None:
    from app.enums.subfield_axis import SubfieldAxis

    assert {m.value for m in SubfieldAxis} == {"horizontal", "vertical", "implicit", "none"}
    assert SubfieldAxis.HORIZONTAL.value == "horizontal"
    assert SubfieldAxis.VERTICAL.value   == "vertical"
    assert SubfieldAxis.IMPLICIT.value   == "implicit"
    assert SubfieldAxis.NONE.value       == "none"


def test_subfield_axis_is_str_enum() -> None:
    from app.enums.subfield_axis import SubfieldAxis

    assert isinstance(SubfieldAxis.HORIZONTAL, str)


def test_judge_decision_values() -> None:
    from app.enums.judge_decision import JudgeDecision

    assert {m.value for m in JudgeDecision} == {"approve", "modify", "escalate"}
    assert JudgeDecision.APPROVE.value  == "approve"
    assert JudgeDecision.MODIFY.value   == "modify"
    assert JudgeDecision.ESCALATE.value == "escalate"


def test_judge_decision_is_str_enum() -> None:
    from app.enums.judge_decision import JudgeDecision

    assert isinstance(JudgeDecision.APPROVE, str)


def test_policy_severity_values() -> None:
    from app.enums.policy_severity import PolicySeverity

    assert {m.value for m in PolicySeverity} == {"info", "warning", "error"}
    assert PolicySeverity.INFO.value    == "info"
    assert PolicySeverity.WARNING.value == "warning"
    assert PolicySeverity.ERROR.value   == "error"


def test_policy_severity_is_str_enum() -> None:
    from app.enums.policy_severity import PolicySeverity

    assert isinstance(PolicySeverity.INFO, str)


def test_cluster_role_values() -> None:
    from app.enums.cluster_role import ClusterRole

    assert {m.value for m in ClusterRole} == {
        "pli_cluster", "metadata_only", "summary", "other",
    }
    assert ClusterRole.PLI_CLUSTER.value   == "pli_cluster"
    assert ClusterRole.METADATA_ONLY.value == "metadata_only"
    assert ClusterRole.SUMMARY.value       == "summary"
    assert ClusterRole.OTHER.value         == "other"


def test_cluster_role_is_str_enum() -> None:
    from app.enums.cluster_role import ClusterRole

    assert isinstance(ClusterRole.PLI_CLUSTER, str)
