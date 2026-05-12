"""Tests for app/services/agents/identity_locator."""
from unittest.mock import MagicMock
from app.models.artifacts import FieldMap, FieldLocation, PLIBoundaries
from app.enums.boundary_pattern import BoundaryPattern
from app.enums.location_pattern import LocationPattern
from app.services.agents.identity_locator import IdentityLocator, SPEC


def test_spec_emits_field_map():
    assert SPEC.name == "identity_locator"
    assert SPEC.output_schema is FieldMap


def test_run_returns_field_map():
    fake_fm = FieldMap(
        sheet="Sheet 1",
        locations=[FieldLocation(field="io_number", pattern=LocationPattern.COLUMN,
                                column="K", data_start_row=4, data_end_row=9,
                                confidence=0.95)],
    )
    boundaries = PLIBoundaries(sheet="Sheet 1", pattern=BoundaryPattern.VERTICAL_MERGE,
                              data_start_row=4, data_end_row=9, confidence=0.9)
    fake_runner = MagicMock()
    fake_runner.run.return_value = fake_fm
    loc = IdentityLocator(llm=MagicMock())
    loc.runner = fake_runner
    out = loc.run(workbook_ctx=MagicMock(), sheet="Sheet 1", boundaries=boundaries)
    assert out["field_map"].locations[0].field == "io_number"
