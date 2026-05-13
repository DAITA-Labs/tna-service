# tests/e2e/test_failure_apply_mismatches.py
"""E2E failure test: apply_plan handles empty CanonicalNameMap gracefully.

With an empty name_map, fields can't be resolved to canonical names. The
pipeline should still produce a (mostly-empty) PLI without crashing.
"""
from app.services.extraction import extract
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("apply_name_map_missing_required")
def test_extract_with_empty_name_map_degrades_gracefully(fixture):
    llm = FakeLLM(canned=fixture.fake_llm_responses())
    result = extract(fixture.xlsx_path, llm=llm)
    e2e = fixture.expectations("e2e")
    assert e2e["pli_count_min"] <= len(result.plis) <= e2e["pli_count_max"]
    for pli in result.plis:
        assert pli.io_number is None or pli.io_number == ""
