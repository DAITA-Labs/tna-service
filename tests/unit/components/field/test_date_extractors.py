"""Delivery / Shipment / ExFty date extractors — shared parametric tests."""
from __future__ import annotations

import datetime as dt

import pytest
from haystack import Pipeline

from app.components.field.delivery_date import DeliveryDateExtractor
from app.components.field.ex_fty_date import ExFtyDateExtractor
from app.components.field.shipment_date import ShipmentDateExtractor
from tests.unit.components.field._bundles import make_bundle


DATE_EXTRACTORS = [
    (DeliveryDateExtractor, "delivery_date"),
    (ShipmentDateExtractor, "shipment_date"),
    (ExFtyDateExtractor, "ex_fty_date"),
]


def _bundle_with(values, canonical, *, axis="vertical", columns=None, rows=None,
                   date_strip_col=None):
    return make_bundle(
        values, canonical,
        axis=axis, columns=columns, rows=rows,
        date_strip_col=date_strip_col,
    )


@pytest.mark.parametrize("extractor_cls,canonical", DATE_EXTRACTORS)
def test_datetime_cells_extracted_as_dates(extractor_cls, canonical) -> None:
    bundle = _bundle_with([
        [None], ["Hdr"],
        [dt.datetime(2026, 5, 27, 9, 0)],
        [dt.datetime(2026, 6, 15, 0, 0)],
    ], canonical, date_strip_col=1)
    out = extractor_cls().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == [dt.date(2026, 5, 27), dt.date(2026, 6, 15)]


@pytest.mark.parametrize("extractor_cls,canonical", DATE_EXTRACTORS)
def test_iso_strings_parsed(extractor_cls, canonical) -> None:
    bundle = _bundle_with([
        [None], ["Hdr"], ["2026-05-27"], ["2026/06/15"],
    ], canonical, date_strip_col=1)
    out = extractor_cls().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == [dt.date(2026, 5, 27), dt.date(2026, 6, 15)]


@pytest.mark.parametrize("extractor_cls,canonical", DATE_EXTRACTORS)
def test_dmy_strings_parsed(extractor_cls, canonical) -> None:
    bundle = _bundle_with([
        [None], ["Hdr"], ["27-05-2026"], ["27/05/26"],
    ], canonical, date_strip_col=1)
    out = extractor_cls().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == [dt.date(2026, 5, 27), dt.date(2026, 5, 27)]


@pytest.mark.parametrize("extractor_cls,canonical", DATE_EXTRACTORS)
def test_named_month_strings_parsed(extractor_cls, canonical) -> None:
    bundle = _bundle_with([
        [None], ["Hdr"], ["27-May-2026"], ["May 27, 2026"],
    ], canonical, date_strip_col=1)
    out = extractor_cls().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == [dt.date(2026, 5, 27), dt.date(2026, 5, 27)]


@pytest.mark.parametrize("extractor_cls,canonical", DATE_EXTRACTORS)
def test_unparseable_and_blank_cells_skipped(extractor_cls, canonical) -> None:
    """Garbage / blanks produce no Finding (no raw value preserved for dates)."""
    bundle = _bundle_with([
        [None], ["Hdr"],
        ["TBD"], [None], [""],
        ["2026-05-27"],
    ], canonical, date_strip_col=1)
    out = extractor_cls().run(bundle=bundle)
    assert [f.value for f in out["findings"]] == [dt.date(2026, 5, 27)]


@pytest.mark.parametrize("extractor_cls,canonical", DATE_EXTRACTORS)
def test_finding_carries_correct_canonical_and_coords(extractor_cls, canonical) -> None:
    bundle = _bundle_with([[None], ["Hdr"], ["2026-05-27"]], canonical, date_strip_col=1)
    out = extractor_cls().run(bundle=bundle)
    f = out["findings"][0]
    assert f.canonical == canonical
    assert f.value_coord == ("A", 3)
    assert f.label_coord == ("A", 2)
    assert "HEADER_BAND_MEMBER" in f.evidence


@pytest.mark.parametrize("extractor_cls,canonical", DATE_EXTRACTORS)
def test_no_candidate_columns_yields_no_findings(extractor_cls, canonical) -> None:
    bundle = _bundle_with([[None], ["Hdr"], ["2026-05-27"]], canonical, columns={},
                            date_strip_col=1)
    assert extractor_cls().run(bundle=bundle)["findings"] == []


@pytest.mark.parametrize("extractor_cls,canonical", DATE_EXTRACTORS)
def test_unsupported_pli_axis_returns_empty(extractor_cls, canonical) -> None:
    for axis in ("sectional", "sheet", "horizontal"):
        bundle = _bundle_with([[None], ["Hdr"], ["2026-05-27"]], canonical, axis=axis,
                                date_strip_col=1)
        assert extractor_cls().run(bundle=bundle)["findings"] == []


@pytest.mark.parametrize("extractor_cls,_canonical", DATE_EXTRACTORS)
def test_extractor_sockets_registered(extractor_cls, _canonical) -> None:
    comp = extractor_cls()
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "findings" in comp.__haystack_output__._sockets_dict


@pytest.mark.parametrize("extractor_cls,canonical", DATE_EXTRACTORS)
def test_extractor_addable_to_pipeline(extractor_cls, canonical) -> None:
    pipeline = Pipeline()
    pipeline.add_component(canonical, extractor_cls())
    assert canonical in pipeline.graph.nodes
