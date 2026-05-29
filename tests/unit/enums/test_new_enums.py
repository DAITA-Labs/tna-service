"""Value + identity coverage for the new enums added in Phase 1 of the
plan-driven canvas architecture."""
from __future__ import annotations


def test_field_location_mode_values() -> None:
    from app.enums.field_location_mode import FieldLocationMode

    assert {m.value for m in FieldLocationMode} == {"column", "kv_block", "missing"}
    assert FieldLocationMode.COLUMN.value    == "column"
    assert FieldLocationMode.KV_BLOCK.value  == "kv_block"
    assert FieldLocationMode.MISSING.value   == "missing"


def test_field_location_mode_is_str_enum() -> None:
    from app.enums.field_location_mode import FieldLocationMode

    assert isinstance(FieldLocationMode.COLUMN, str)
    assert FieldLocationMode.COLUMN == "column"
