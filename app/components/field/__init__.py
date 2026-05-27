"""Per-canonical field extractors — emit Findings from a ClusterAnchorBundle.

Each identifier extractor is a standalone Haystack `@component class` with
its own `run(bundle)` method covering one of the 11 identifier canonicals.
The `MetadataExtractor` is the open-vocabulary counterpart: one component
that walks every KvBlock not already claimed by an identifier / stage
Finding and emits a `MetadataEntry` for each — supporting novel labels
without schema changes.
"""
from app.components.field.arbiter import IdentifierArbiter
from app.components.field.color_code import ColorCodeExtractor
from app.components.field.color_name import ColorNameExtractor
from app.components.field.delivery_date import DeliveryDateExtractor
from app.components.field.ex_fty_date import ExFtyDateExtractor
from app.components.field.fabric_code import FabricCodeExtractor
from app.components.field.fabric_name import FabricNameExtractor
from app.components.field.io_number import IoNumberExtractor
from app.components.field.metadata import MetadataExtractor
from app.components.field.quantity import QuantityExtractor
from app.components.field.shipment_date import ShipmentDateExtractor
from app.components.field.style_code import StyleCodeExtractor
from app.components.field.style_name import StyleNameExtractor

__all__ = [
    "ColorCodeExtractor",
    "ColorNameExtractor",
    "DeliveryDateExtractor",
    "ExFtyDateExtractor",
    "FabricCodeExtractor",
    "FabricNameExtractor",
    "IdentifierArbiter",
    "IoNumberExtractor",
    "MetadataExtractor",
    "QuantityExtractor",
    "ShipmentDateExtractor",
    "StyleCodeExtractor",
    "StyleNameExtractor",
]
