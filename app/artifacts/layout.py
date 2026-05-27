"""LayoutHint + LayoutAxes — the artifact emitted by StructurePhase.

Bridges structure-phase analysis (canvas channels + StructureBag) and
field-phase extraction (per-canonical components). A single LayoutHint
is computed per `pli_cluster` from the cluster's anchor sheet and shared
across the cluster's other sheets.

Layout has three orthogonal axes:
  PliAxis      — along which PLIs iterate (vertical / sectional / sheet)
  StageAxis    — along which stages iterate within a PLI
  SubfieldAxis — along which subfields iterate within a stage

Field components consume `candidate_columns`, `candidate_rows`, and
`candidate_kv_blocks` to narrow their search space; they do not re-scan
the canvas for label cells.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.artifacts.structure import (
    DataRowRange,
    HeaderBand,
    KvBlock,
    SectionBoundary,
    StageArena,
    StageBand,
    SubfieldCluster,
)


Direction = Literal[
    "vertical",
    "horizontal",
    "sheet",
    "sectional",
    "none",
    "implicit",
    "unknown",
]


@dataclass
class LayoutAxes:
    """Three orthogonal axes describing how a sheet is laid out.

    Each axis carries its own confidence in `confidence` keyed by axis name.
    Components consult both the axis value and its confidence when deciding
    whether to invoke a judge.
    """

    pli_axis:      Direction
    stage_axis:    Direction
    subfield_axis: Direction
    confidence:    dict[str, float] = field(default_factory=dict)


@dataclass
class LayoutHint:
    """All structural facts a field component needs to extract from a sheet.

    Shared across sheets within one `pli_cluster` (one LayoutHint per cluster,
    anchored to the cluster's template sheet). Field components consume the
    typed records and candidate dicts here; they do not reach into raw
    canvas channels for spatial reasoning.

    Attributes:
        axes:                 the inferred PliAxis / StageAxis / SubfieldAxis
        cluster_id:           stable identifier within the workbook
        confidence:           overall confidence in the hint (0..1)
        header_band:          the detected header band, if any
        data_row_ranges:      contiguous PLI data row ranges
        section_boundaries:   SECTION_PER_PLI section starts (when applicable)
        stage_arenas:         StageArena rectangles (one per arena)
        stage_bands:          StageBand records inside arenas
        subfield_clusters:    SubfieldCluster records inside bands
        kv_blocks:             KvBlock pairs (SHEET_IS_PLI / scattered metadata)
        candidate_columns:    canonical → list of candidate column indices
        candidate_rows:       canonical → list of candidate row indices
        candidate_kv_blocks:  canonical → list of candidate KvBlocks
    """

    axes:        LayoutAxes
    cluster_id:  str
    confidence:  float

    header_band:        HeaderBand | None = None
    data_row_ranges:    list[DataRowRange] = field(default_factory=list)
    section_boundaries: list[SectionBoundary] = field(default_factory=list)
    stage_arenas:       list[StageArena] = field(default_factory=list)
    stage_bands:        list[StageBand] = field(default_factory=list)
    subfield_clusters:  list[SubfieldCluster] = field(default_factory=list)
    kv_blocks:          list[KvBlock] = field(default_factory=list)

    candidate_columns:   dict[str, list[int]] = field(default_factory=dict)
    candidate_rows:      dict[str, list[int]] = field(default_factory=dict)
    candidate_kv_blocks: dict[str, list[KvBlock]] = field(default_factory=dict)
