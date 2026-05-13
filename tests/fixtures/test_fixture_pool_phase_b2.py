from tests.fixtures.case import fixture_case


@fixture_case("sheet_per_pli_clean", "row_per_pli_with_merges", "section_per_pli_two_blocks")
def test_phase_b2_fixtures_load(fixture):
    assert fixture.xlsx_path.exists()
    assert "flow" in fixture._expected["layer_expectations"]
    assert "e2e" in fixture._expected["layer_expectations"]
