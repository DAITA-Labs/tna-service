"""Structure phase resolvers — interpret pattern records into semantic roles.

Each resolver is a plain function over (canvas, StructureBag) that
appends semantic records back into the bag. The structure phase
orchestrator (Tier 2c) calls them in dependency order:

  HeaderBandResolver
    → DataRowRangeResolver
    → SectionBoundaryResolver
    → StageArenaResolver
       → StageBandResolver
          → SubfieldClusterResolver
"""
from __future__ import annotations

from app.components.structure.resolvers.data_row_range import resolve_data_row_ranges
from app.components.structure.resolvers.header_band import resolve_header_band
from app.components.structure.resolvers.section_boundary import resolve_section_boundaries
from app.components.structure.resolvers.stage_arena import resolve_stage_arenas
from app.components.structure.resolvers.stage_band import resolve_stage_bands
from app.components.structure.resolvers.subfield_cluster import resolve_subfield_clusters

__all__ = [
    "resolve_data_row_ranges",
    "resolve_header_band",
    "resolve_section_boundaries",
    "resolve_stage_arenas",
    "resolve_stage_bands",
    "resolve_subfield_clusters",
]
