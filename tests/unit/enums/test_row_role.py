from app.enums.row_role import RowRole, SubRowRole


def test_row_role_values():
    assert RowRole.TITLE.value == "title"
    assert RowRole.HEADER.value == "header"
    assert RowRole.ANCHOR.value == "anchor"
    assert RowRole.CHILD.value == "child"
    assert RowRole.TOTAL.value == "total"
    assert RowRole.GRAND_TOTAL.value == "grand_total"
    assert RowRole.REPEAT_HEADER.value == "repeat_header"
    assert RowRole.BLANK.value == "blank"
    assert RowRole.SEPARATOR.value == "separator"


def test_sub_row_role_values():
    assert SubRowRole.PLAN.value == "plan"
    assert SubRowRole.ACTION.value == "action"
    assert SubRowRole.ACTUAL.value == "actual"
    assert SubRowRole.DEVIATION.value == "deviation"
