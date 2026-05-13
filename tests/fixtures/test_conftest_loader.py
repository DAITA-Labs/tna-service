"""Tests for the conftest-defined `fixture` pytest fixture."""
import pytest
from tests.fixtures.case import fixture_case


@fixture_case("_smoke")
def test_loader_materializes_xlsx_and_parses_expected(fixture):
    assert fixture.name == "_smoke"
    assert fixture.xlsx_path is not None
    assert fixture.xlsx_path.exists()
    assert fixture.expectations("flow") == {"pli_mode": "row_per_pli"}
