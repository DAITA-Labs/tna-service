"""Agent test: SheetClassifier behaviour under canned LLM responses."""
from app.components.sheet_classifier import SheetClassifier
from app.tools._registry import TOOL_REGISTRY
import app.tools.survey  # noqa: F401 — register tools
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("tabular_simple")
def test_sheet_classifier_returns_canned_relevant_sheets(fixture):
    e2e = fixture.expectations("e2e")
    fake_responses = e2e["fake_llm_responses"]
    llm = FakeLLM(canned={"SheetClassifierOutput": fake_responses["SheetClassifierOutput"]})
    summary = TOOL_REGISTRY.get("workbook_summary")(fixture.ctx)
    out = SheetClassifier(llm=llm).run(workbook_ctx=fixture.ctx, workbook_summary=summary)
    assert out["relevant_sheets"] == fake_responses["SheetClassifierOutput"]["relevant_sheets"]
