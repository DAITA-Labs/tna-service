from app.enums.stage_scope import StageScope


def test_stage_scope_values():
    assert StageScope.SHEET_LEVEL.value == "sheet_level"
    assert StageScope.SECTION_LOCAL.value == "section_local"
    assert StageScope.PLI_LOCAL.value == "pli_local"
