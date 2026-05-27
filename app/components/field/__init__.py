"""Per-canonical field extractors — emit Findings from a ClusterAnchorBundle.

Each extractor is a standalone Haystack `@component class` with its own
`run(bundle)` method. They share no template base class — different
canonicals have different extraction shapes (some read columns, some
read KvBlocks, some derive from other findings).
"""
from app.components.field.io_number import IoNumberExtractor
from app.components.field.quantity import QuantityExtractor

__all__ = ["IoNumberExtractor", "QuantityExtractor"]
