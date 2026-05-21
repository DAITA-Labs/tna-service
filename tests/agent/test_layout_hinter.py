"""Agent test: LayoutHinter self-aware component under canned response."""
import app.tools.bulk_read  # noqa: F401 — register tools
import app.tools.survey  # noqa: F401 — register tools
from structlog.testing import capture_logs

from app.components.per_sheet.layout_hinter import LayoutHinter
from app.components.planner.plan import SheetRowPlanner
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import ValidationFinding
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("tabular_corrupt_no_identity_col")
def test_layout_hinter_returns_canned_hints(fixture):
    """When Tier-1 errors exist, LayoutHinter invokes LLM and applies non-null suggestions."""
    e2e = fixture.expectations("e2e")
    canned = e2e["fake_llm_responses"]["LayoutHints"]
    llm = FakeLLM(canned={"LayoutHints": canned})
    # Inject a synthetic error so the hinter triggers the LLM path.
    error_finding = ValidationFinding(
        check="test_error", severity=ValidationSeverity.ERROR, message="force hinter",
    )
    with capture_logs():
        plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
        out = LayoutHinter(llm=llm).run(
            workbook_ctx=fixture.ctx,
            plan=plan,
            findings=[error_finding],
            sheet=fixture.sheet,
        )
    suggestion = canned.get("identity_column_suggestion")
    if suggestion:
        # A non-null suggestion must be applied to the plan.
        assert out["plan"].identity_column == suggestion
    else:
        # Null suggestion → plan returned unchanged; identity_column from planner kept.
        assert out["plan"].identity_column == plan.identity_column
