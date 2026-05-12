"""Tests for app/services/agents/quantity_date_locator."""
from unittest.mock import MagicMock
from app.models.artifacts import FieldMap, FieldLocation, PLIBoundaries
from app.enums.boundary_pattern import BoundaryPattern
from app.enums.location_pattern import LocationPattern
from app.services.agents.quantity_date_locator import QuantityDateLocator, SPEC


def test_spec_emits_field_map():
    assert SPEC.name == "quantity_date_locator"
    assert SPEC.output_schema is FieldMap


def test_run_returns_field_map():
    fake_fm = FieldMap(
        sheet="Sheet 1",
        locations=[
            FieldLocation(field="quantity", pattern=LocationPattern.COLUMN, column="M",
                         data_start_row=4, data_end_row=9, confidence=0.9),
            FieldLocation(field="delivery_date", pattern=LocationPattern.COLUMN, column="P",
                         data_start_row=4, data_end_row=9, confidence=0.95),
        ],
    )
    boundaries = PLIBoundaries(sheet="Sheet 1", pattern=BoundaryPattern.VERTICAL_MERGE,
                              data_start_row=4, data_end_row=9, confidence=0.9)
    fake_runner = MagicMock()
    fake_runner.run.return_value = fake_fm
    loc = QuantityDateLocator(llm=MagicMock())
    loc.runner = fake_runner
    out = loc.run(workbook_ctx=MagicMock(), sheet="Sheet 1", boundaries=boundaries)
    fields = {l.field for l in out["field_map"].locations}
    assert fields == {"quantity", "delivery_date"}
