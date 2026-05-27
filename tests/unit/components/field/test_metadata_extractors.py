"""Buyer / Season / Factory / OrderReceiptDate — KvBlock-based metadata extractors."""
from __future__ import annotations

import datetime as dt

import pytest
from haystack import Pipeline

from app.artifacts.structure import KvBlock
from app.components.field.buyer import BuyerExtractor
from app.components.field.factory import FactoryExtractor
from app.components.field.order_receipt_date import OrderReceiptDateExtractor
from app.components.field.season import SeasonExtractor
from tests.unit.components.field._bundles import make_bundle


# String-valued metadata extractors share the same shape.
STRING_METADATA_EXTRACTORS = [
    (BuyerExtractor, "buyer", "Acme Apparel"),
    (SeasonExtractor, "season", "FW26"),
    (FactoryExtractor, "factory", "Unit-7"),
]


def _bundle_with_kv(canonical: str, label: str, value, *,
                       label_coord=("A", 4), value_coord=("B", 4)) -> "ClusterAnchorBundle":
    """Build a bundle whose canvas has the (label, value) cells installed at the kv coords."""
    # The canvas needs the value cell populated; put both label + value in the grid.
    cells = [[None] * 3 for _ in range(5)]
    # Convert column letter to index for both coords
    for (col_letter, row), text in [(label_coord, label), (value_coord, value)]:
        col_idx = ord(col_letter) - ord("A") + 1
        cells[row - 1][col_idx - 1] = text

    kv = KvBlock(
        label_coord=label_coord, value_coord=value_coord,
        label_text=label.lower(), value_dtype=4,  # STR
    )
    return make_bundle(
        cells, canonical,
        columns={},   # metadata doesn't use candidate_columns
        rows={},
        candidate_kv_blocks={canonical: [kv]},
    )


# ─── String metadata extractors (parametric) ───────────────────────────────


@pytest.mark.parametrize("extractor_cls,canonical,sample_value", STRING_METADATA_EXTRACTORS)
def test_string_metadata_emits_one_finding(extractor_cls, canonical, sample_value) -> None:
    bundle = _bundle_with_kv(canonical, label=canonical.title(), value=sample_value)
    out = extractor_cls().run(bundle=bundle)
    assert len(out["findings"]) == 1
    f = out["findings"][0]
    assert f.canonical == canonical
    assert f.value == sample_value


@pytest.mark.parametrize("extractor_cls,canonical,_v", STRING_METADATA_EXTRACTORS)
def test_string_metadata_whitespace_stripped(extractor_cls, canonical, _v) -> None:
    bundle = _bundle_with_kv(canonical, label=canonical.title(), value="  Padded Value  ")
    f = extractor_cls().run(bundle=bundle)["findings"][0]
    assert f.value == "Padded Value"


@pytest.mark.parametrize("extractor_cls,canonical,_v", STRING_METADATA_EXTRACTORS)
def test_no_candidate_kv_block_yields_no_findings(extractor_cls, canonical, _v) -> None:
    bundle = make_bundle(
        [[None] * 3 for _ in range(5)], canonical,
        columns={}, rows={}, candidate_kv_blocks={},
    )
    assert extractor_cls().run(bundle=bundle)["findings"] == []


@pytest.mark.parametrize("extractor_cls,canonical,_v", STRING_METADATA_EXTRACTORS)
def test_blank_value_cell_yields_no_findings(extractor_cls, canonical, _v) -> None:
    bundle = _bundle_with_kv(canonical, label=canonical.title(), value=None)
    assert extractor_cls().run(bundle=bundle)["findings"] == []


@pytest.mark.parametrize("extractor_cls,canonical,_v", STRING_METADATA_EXTRACTORS)
def test_finding_carries_label_and_value_coords(extractor_cls, canonical, _v) -> None:
    bundle = _bundle_with_kv(canonical, label=canonical.title(), value="x",
                                 label_coord=("A", 4), value_coord=("B", 4))
    f = extractor_cls().run(bundle=bundle)["findings"][0]
    assert f.label_coord == ("A", 4)
    assert f.value_coord == ("B", 4)
    assert "KV_BLOCK_MATCH" in f.evidence


@pytest.mark.parametrize("extractor_cls,_canonical,_v", STRING_METADATA_EXTRACTORS)
def test_extractor_sockets_registered(extractor_cls, _canonical, _v) -> None:
    comp = extractor_cls()
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "findings" in comp.__haystack_output__._sockets_dict


@pytest.mark.parametrize("extractor_cls,canonical,_v", STRING_METADATA_EXTRACTORS)
def test_extractor_addable_to_pipeline(extractor_cls, canonical, _v) -> None:
    pipeline = Pipeline()
    pipeline.add_component(canonical, extractor_cls())
    assert canonical in pipeline.graph.nodes


# ─── OrderReceiptDateExtractor (date-valued) ───────────────────────────────


def test_order_receipt_date_datetime_value_extracted() -> None:
    bundle = _bundle_with_kv(
        "order_receipt_date",
        label="Order Receipt Date",
        value=dt.datetime(2026, 5, 27, 9, 0),
    )
    out = OrderReceiptDateExtractor().run(bundle=bundle)
    f = out["findings"][0]
    assert f.value == dt.date(2026, 5, 27)
    assert f.canonical == "order_receipt_date"


def test_order_receipt_date_iso_string_parsed() -> None:
    bundle = _bundle_with_kv(
        "order_receipt_date", label="Order Receipt Date", value="2026-05-27",
    )
    f = OrderReceiptDateExtractor().run(bundle=bundle)["findings"][0]
    assert f.value == dt.date(2026, 5, 27)


def test_order_receipt_date_unparseable_yields_no_findings() -> None:
    """Garbage string in the value cell → no Finding (dates must parse cleanly)."""
    bundle = _bundle_with_kv("order_receipt_date", label="Order Receipt Date", value="TBD")
    assert OrderReceiptDateExtractor().run(bundle=bundle)["findings"] == []


def test_order_receipt_date_no_candidate_kv_yields_no_findings() -> None:
    bundle = make_bundle(
        [[None] * 3 for _ in range(5)], "order_receipt_date",
        columns={}, rows={}, candidate_kv_blocks={},
    )
    assert OrderReceiptDateExtractor().run(bundle=bundle)["findings"] == []
