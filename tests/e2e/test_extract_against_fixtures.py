"""End-to-end test: full extract() pipeline with FakeLLM against fixtures."""
from app.services.extraction import extract
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case(
    "tabular_simple", "tabular_with_totals", "row_per_pli_with_merges",
    "sheet_per_pli_clean",
)
def test_extract_emits_expected_plis(fixture):
    llm = FakeLLM(canned=fixture.fake_llm_responses())
    result = extract(fixture.xlsx_path, llm=llm)
    e2e = fixture.expectations("e2e")
    assert len(result.plis) == e2e["pli_count"]
    expected_ios = e2e["io_numbers"]
    actual_ios = [p.io_number for p in result.plis]
    assert sorted(actual_ios) == sorted(expected_ios)
