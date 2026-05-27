"""MetadataExtractor — open-vocabulary sheet metadata."""
from __future__ import annotations

import datetime as dt

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding
from app.artifacts.structure import KvBlock
from app.components.field.metadata import MetadataExtractor
from app.specs.enums import FieldScope
from tests.unit.components.field._bundles import make_bundle


def _bundle_with_kvs(kvs_with_values: list[tuple[KvBlock, object]]):
    """Build a bundle whose bag carries `kvs` and whose canvas has the value cells set.

    Each tuple is (kv, value_to_install). The value cell is populated at
    kv.value_coord; the label cell at kv.label_coord is also populated with
    the label_text so the structural picture is plausible.
    """
    cells = [[None] * 10 for _ in range(20)]
    for kv, value in kvs_with_values:
        for (col_letter, row), payload in [
            (kv.label_coord, kv.label_text),
            (kv.value_coord, value),
        ]:
            col_idx = ord(col_letter) - ord("A") + 1
            cells[row - 1][col_idx - 1] = payload

    bundle = make_bundle(cells, "buyer", columns={}, rows={})
    bundle.bag.kv_blocks = [kv for kv, _ in kvs_with_values]
    return bundle


def _kv(label: str, *, label_coord, value_coord) -> KvBlock:
    return KvBlock(
        label_coord=label_coord, value_coord=value_coord,
        label_text=label, value_dtype=4,
    )


def test_empty_kv_blocks_yields_no_entries() -> None:
    bundle = make_bundle([[None] * 3 for _ in range(5)], "buyer",
                         columns={}, rows={})
    out = MetadataExtractor().run(bundle=bundle)
    assert out["metadata"] == []


def test_kv_block_with_known_canonical_label_sets_canonical() -> None:
    """A label matching METADATA_SPECS alias gets its canonical name."""
    kv = _kv("Buyer", label_coord=("A", 4), value_coord=("B", 4))
    bundle = _bundle_with_kvs([(kv, "Acme Apparel")])

    entries = MetadataExtractor().run(bundle=bundle)["metadata"]
    assert len(entries) == 1
    e = entries[0]
    assert e.key == "Buyer"
    assert e.canonical == "buyer"
    assert e.value == "Acme Apparel"
    assert e.source == "B4"
    assert e.scope == FieldScope.SHEET


def test_kv_block_with_novel_label_canonical_is_none() -> None:
    """Labels not in METADATA_SPECS pass through with canonical=None."""
    kv = _kv("Treatment", label_coord=("A", 5), value_coord=("B", 5))
    bundle = _bundle_with_kvs([(kv, "Stone wash")])

    e = MetadataExtractor().run(bundle=bundle)["metadata"][0]
    assert e.key == "Treatment"
    assert e.canonical is None
    assert e.value == "Stone wash"


def test_multiple_kv_blocks_all_emit_entries() -> None:
    kvs = [
        (_kv("Buyer", label_coord=("A", 4), value_coord=("B", 4)), "Acme"),
        (_kv("Season", label_coord=("A", 5), value_coord=("B", 5)), "FW26"),
        (_kv("Booking Ref", label_coord=("A", 6), value_coord=("B", 6)), "BR-001"),
    ]
    bundle = _bundle_with_kvs(kvs)

    entries = MetadataExtractor().run(bundle=bundle)["metadata"]
    assert [e.key for e in entries] == ["Buyer", "Season", "Booking Ref"]
    assert [e.canonical for e in entries] == ["buyer", "season", None]


def test_prior_findings_claim_kv_blocks() -> None:
    """A KvBlock whose value_coord is claimed by an identifier Finding is skipped."""
    io_kv = _kv("IO No", label_coord=("A", 4), value_coord=("B", 4))
    buyer_kv = _kv("Buyer", label_coord=("A", 5), value_coord=("B", 5))
    bundle = _bundle_with_kvs([(io_kv, "IO-1063"), (buyer_kv, "Acme")])

    # IoNumberExtractor would have emitted a Finding at ("B", 4).
    prior = [Finding(
        canonical="io_number",
        label_coord=("A", 4), value_coord=("B", 4),
        value="IO-1063", confidence=Confidence.HIGH, evidence=[],
    )]

    entries = MetadataExtractor().run(bundle=bundle, prior_findings=prior)["metadata"]
    # Only Buyer remains — IO No was claimed.
    assert [e.key for e in entries] == ["Buyer"]
    assert entries[0].canonical == "buyer"


def test_blank_value_cell_skipped() -> None:
    kv = _kv("Buyer", label_coord=("A", 4), value_coord=("B", 4))
    bundle = _bundle_with_kvs([(kv, None)])
    assert MetadataExtractor().run(bundle=bundle)["metadata"] == []


def test_order_receipt_date_parsed_to_date() -> None:
    """Known date-typed metadata canonical → value goes through parse_date."""
    kv = _kv("Order Receipt Date", label_coord=("A", 4), value_coord=("B", 4))
    bundle = _bundle_with_kvs([(kv, "2026-05-27")])

    e = MetadataExtractor().run(bundle=bundle)["metadata"][0]
    assert e.canonical == "order_receipt_date"
    assert e.value == dt.date(2026, 5, 27)


def test_novel_label_string_stripped() -> None:
    kv = _kv("Treatment", label_coord=("A", 4), value_coord=("B", 4))
    bundle = _bundle_with_kvs([(kv, "  Stone wash  ")])
    e = MetadataExtractor().run(bundle=bundle)["metadata"][0]
    assert e.value == "Stone wash"


def test_normalised_label_matching_handles_hyphens() -> None:
    """Label 'Order-Receipt' should still match the 'order receipt' alias."""
    kv = _kv("Order-Receipt", label_coord=("A", 4), value_coord=("B", 4))
    bundle = _bundle_with_kvs([(kv, "2026-05-27")])

    e = MetadataExtractor().run(bundle=bundle)["metadata"][0]
    assert e.canonical == "order_receipt_date"


def test_extractor_sockets_registered() -> None:
    comp = MetadataExtractor()
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "prior_findings" in comp.__haystack_input__._sockets_dict
    assert "metadata" in comp.__haystack_output__._sockets_dict


def test_extractor_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("metadata", MetadataExtractor())
    assert "metadata" in pipeline.graph.nodes
