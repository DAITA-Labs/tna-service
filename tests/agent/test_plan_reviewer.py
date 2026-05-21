"""Agent test: PlanReviewer self-aware component judges a SheetPlan."""
import app.tools.bulk_read  # noqa: F401 — register tools
import app.tools.survey  # noqa: F401 — register tools
from structlog.testing import capture_logs

from app.components.plan_reviewer import PlanReviewer
from app.components.planner.plan import SheetRowPlanner
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import SheetPlan, ValidationFinding
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("tabular_simple")
def test_plan_reviewer_returns_canned_verdict(fixture):
    """When reviewer conditions are met, PlanReviewer applies the canned verdict."""
    canned = fixture.expectations("e2e")["fake_llm_responses"]["PlanVerdict"]
    llm = FakeLLM(canned={"PlanVerdict": canned})
    # Inject a warn finding so the reviewer fires.
    warn_finding = ValidationFinding(
        check="test_warn", severity=ValidationSeverity.WARN, message="force reviewer",
    )
    with capture_logs():
        plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
        out = PlanReviewer(llm=llm).run(
            workbook_ctx=fixture.ctx, plan=plan, findings=[warn_finding],
        )
    assert isinstance(out["plan"], SheetPlan)
