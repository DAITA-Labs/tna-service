from tests.fixtures.case import fixture_case


@fixture_case("workbook_only_title_row", "tabular_corrupt_no_identity_col", "stage_band_low_date_density")
def test_phase_b3_fixtures_load(fixture):
    assert fixture.is_failure_case()
    assert fixture.failure_expectations()["graceful_degradation"] is True
