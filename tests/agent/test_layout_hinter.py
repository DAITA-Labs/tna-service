"""Agent test: LayoutHinter under canned response."""
from app.components.layout_hinter import LayoutHinter
from app.components.planner.surveyor import survey_sheet
import app.tools.survey  # noqa: F401 — register tools
import app.tools.bulk_read  # noqa: F401 — register tools
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("tabular_corrupt_no_identity_col")
def test_layout_hinter_returns_canned_hints(fixture):
    e2e = fixture.expectations("e2e")
    canned = e2e["fake_llm_responses"]["LayoutHints"]
    llm = FakeLLM(canned={"LayoutHints": canned})
    signals = survey_sheet(fixture.ctx, fixture.sheet)
    out = LayoutHinter(llm=llm).run(
        workbook_ctx=fixture.ctx, sheet=fixture.sheet, signals=signals,
    )
    assert out["hints"].identity_column_suggestion == canned.get("identity_column_suggestion")
