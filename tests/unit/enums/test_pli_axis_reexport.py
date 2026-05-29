"""PliAxis was moved to app/enums/pli_axis.py; legacy imports must still work."""
from __future__ import annotations


def test_pli_axis_importable_from_enums() -> None:
    from app.enums.pli_axis import PliAxis

    assert hasattr(PliAxis, "ROW")
    assert hasattr(PliAxis, "COLUMN")
    assert hasattr(PliAxis, "WHOLE_SHEET")
    assert hasattr(PliAxis, "SECTION")
    assert {m.value for m in PliAxis} == {"row", "column", "whole_sheet", "section"}


def test_pli_axis_legacy_import_path_preserved() -> None:
    from app.enums.pli_axis import PliAxis as Canonical
    from app.specs.enums import PliAxis as Legacy

    assert Canonical is Legacy


def test_pli_axis_is_str_enum() -> None:
    from app.enums.pli_axis import PliAxis

    assert isinstance(PliAxis.ROW, str)
    assert PliAxis.ROW == "row"
