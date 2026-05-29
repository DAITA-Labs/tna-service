"""Canvas-architecture per-bundle extraction pipeline factory.

Wires the eleven per-canonical extractors + arbiter + stage extractor +
metadata extractor into a single Haystack `Pipeline` that operates on
ONE `ClusterAnchorBundle` at a time.

Topology (DAG):

  bundle ─┬─► io_number      ─► findings ─┐
          ├─► quantity                    │
          ├─► style_code                  │
          ├─► color_code                  │
          ├─► fabric_code                 │
          ├─► style_name                  ├──► combiner ──► arbiter ──► findings
          ├─► color_name                  │       (concat)    (dedup)
          ├─► fabric_name                 │                      │
          ├─► delivery_date               │                      │
          ├─► shipment_date               │                      └─► metadata.prior_findings
          ├─► ex_fty_date     ─► findings ┘                          │
          ├─► stages           ───────────► stages_per_row           │
          └─► metadata         ───────────► metadata ◄───────────────┘

The pipeline is purely deterministic — no LLM. All judge / validator
work happens in the sibling `canvas_validators` and `canvas_judges`
pipelines, chained by the service layer.

The service is responsible for calling `WorkbookPhase` first to
produce a `list[ClusterAnchorBundle]`, then running this pipeline
once per bundle and merging the per-bundle outputs.
"""
from __future__ import annotations

from haystack import Pipeline

from app.components.field import (
    ColorCodeExtractor,
    ColorNameExtractor,
    DeliveryDateExtractor,
    ExFtyDateExtractor,
    FabricCodeExtractor,
    FabricNameExtractor,
    IdentifierArbiter,
    IoNumberExtractor,
    MetadataExtractor,
    QuantityExtractor,
    ShipmentDateExtractor,
    StageExtractor,
    StyleCodeExtractor,
    StyleNameExtractor,
)
from app.components.field.canonical_findings_combiner import (
    CanonicalFindingsCombiner,
)


_PER_CANONICAL_EXTRACTORS: tuple[tuple[str, type], ...] = (
    ("io_number",     IoNumberExtractor),
    ("quantity",      QuantityExtractor),
    ("style_code",    StyleCodeExtractor),
    ("color_code",    ColorCodeExtractor),
    ("fabric_code",   FabricCodeExtractor),
    ("style_name",    StyleNameExtractor),
    ("color_name",    ColorNameExtractor),
    ("fabric_name",   FabricNameExtractor),
    ("delivery_date", DeliveryDateExtractor),
    ("shipment_date", ShipmentDateExtractor),
    ("ex_fty_date",   ExFtyDateExtractor),
)


def make_canvas_extract_pipeline() -> Pipeline:
    """Return a per-bundle extraction Pipeline. No LLM provider needed."""
    pipeline = Pipeline()

    for name, cls in _PER_CANONICAL_EXTRACTORS:
        pipeline.add_component(name, cls())
    pipeline.add_component("combiner", CanonicalFindingsCombiner())
    pipeline.add_component("arbiter",  IdentifierArbiter())
    pipeline.add_component("stages",   StageExtractor())
    pipeline.add_component("metadata", MetadataExtractor())

    # Per-canonical findings → combiner.<canonical>_findings
    for name, _cls in _PER_CANONICAL_EXTRACTORS:
        pipeline.connect(f"{name}.findings", f"combiner.{name}_findings")

    # combiner → arbiter, arbiter → metadata.prior_findings
    pipeline.connect("combiner.findings", "arbiter.findings")
    pipeline.connect("arbiter.findings",  "metadata.prior_findings")

    return pipeline
