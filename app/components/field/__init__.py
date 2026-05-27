"""Per-canonical field components — emit Findings from a ClusterAnchorBundle."""
from app.components.field._base import BaseCanonicalComponent
from app.components.field.io_number import IoNumberComponent, IoNumberExtractor

__all__ = [
    "BaseCanonicalComponent",
    "IoNumberComponent",
    "IoNumberExtractor",
]
