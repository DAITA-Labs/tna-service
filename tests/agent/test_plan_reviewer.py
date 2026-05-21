"""Agent test: PlanReviewer judges a SheetPlan."""
from app.components.plan_reviewer import PlanReviewer
from app.services.planner.plan import SheetRowPlanner
import app.repositories.workbook_tools.survey  # noqa: F401 — register tools
import app.repositories.workbook_tools.bulk_read  # noqa: F401 — register tools
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("tabular_simple")
def test_plan_reviewer_returns_canned_verdict(fixture):
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    canned = fixture.expectations("e2e")["fake_llm_responses"]["PlanVerdict"]
    llm = FakeLLM(canned={"PlanVerdict": canned})
    out = PlanReviewer(llm=llm).run(workbook_ctx=fixture.ctx, plan=plan, findings=[])
    assert out["verdict"].verdict == canned["verdict"]
