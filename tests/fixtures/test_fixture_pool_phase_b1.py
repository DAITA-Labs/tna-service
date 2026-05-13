"""Smoke-test that the Phase B1 fixtures load via the conftest loader."""
from tests.fixtures.case import fixture_case


@fixture_case("tabular_simple", "tabular_with_totals", "tabular_repeat_header")
def test_phase_b1_fixtures_load(fixture):
    assert fixture.xlsx_path is not None
    assert fixture.xlsx_path.exists()
    assert "flow" in fixture._expected["layer_expectations"]
    assert "e2e" in fixture._expected["layer_expectations"]
