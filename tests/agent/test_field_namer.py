"""Agent test: FieldNamer maps labels to canonical names."""
from app.components.field_namer import FieldNamer
from app.components.planner.plan import SheetRowPlanner
import app.tools.survey  # noqa: F401 — register tools
import app.tools.bulk_read  # noqa: F401 — register tools
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("tabular_simple")
def test_field_namer_returns_canned_canonical_map(fixture):
    plan = SheetRowPlanner().run(workbook_ctx=fixture.ctx, sheet=fixture.sheet)["plan"]
    canned = fixture.expectations("e2e")["fake_llm_responses"]["CanonicalNameMap"]
    llm = FakeLLM(canned={"CanonicalNameMap": canned})
    out = FieldNamer(llm=llm).run(workbook_ctx=fixture.ctx, plan=plan)
    assert out["name_map"].field_labels == canned["field_labels"]
