# tests/e2e/test_failure_input_validation.py
"""E2E failure test: input validation — title-only workbook returns empty plis without crashing."""
from structlog.testing import capture_logs

from app.services.extract_service import extract
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("workbook_only_title_row")
def test_extract_handles_title_only_workbook(fixture):
    llm = FakeLLM(canned=fixture.fake_llm_responses())
    with capture_logs():
        result = extract(fixture.xlsx_path, llm=llm)
    failure = fixture.failure_expectations()
    assert failure["graceful_degradation"] is True
    e2e = fixture.expectations("e2e")
    assert len(result.plis) == e2e["pli_count"]
    assert result.source_file is not None
