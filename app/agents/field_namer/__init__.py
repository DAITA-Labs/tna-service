"""FieldNamer agent — maps detected labels and stage headers to canonical names."""
from __future__ import annotations

from app.agents.field_namer.agent import FieldNamerAgent
from app.agents.field_namer.schema import CanonicalNameMap, FieldNamerInputs

__all__ = ["CanonicalNameMap", "FieldNamerAgent", "FieldNamerInputs"]
