"""Per-canonical field extractors — emit Findings from a ClusterAnchorBundle.

Each extractor is a standalone Haystack `@component class` with its own
`run(bundle)` method. They share no template base class — different
canonicals have different extraction shapes (some read columns, some
read KvBlocks, some derive from other findings).
"""
from app.components.field.color_code import ColorCodeExtractor
from app.components.field.delivery_date import DeliveryDateExtractor
from app.components.field.ex_fty_date import ExFtyDateExtractor
from app.components.field.fabric_code import FabricCodeExtractor
from app.components.field.io_number import IoNumberExtractor
from app.components.field.quantity import QuantityExtractor
from app.components.field.shipment_date import ShipmentDateExtractor
from app.components.field.style_code import StyleCodeExtractor

__all__ = [
    "ColorCodeExtractor",
    "DeliveryDateExtractor",
    "ExFtyDateExtractor",
    "FabricCodeExtractor",
    "IoNumberExtractor",
    "QuantityExtractor",
    "ShipmentDateExtractor",
    "StyleCodeExtractor",
]
