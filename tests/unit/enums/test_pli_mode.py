from app.enums.pli_mode import PliMode


def test_pli_mode_values():
    assert PliMode.ROW_PER_PLI.value == "row_per_pli"
    assert PliMode.SECTION_PER_PLI.value == "section_per_pli"
    assert PliMode.SHEET_IS_PLI.value == "sheet_is_pli"


def test_pli_mode_members_count():
    assert len(list(PliMode)) == 3
