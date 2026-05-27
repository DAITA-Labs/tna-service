"""Role classifier + sheet selector — label clusters as `pli_cluster` or `other_sheets`.

A cluster is a `pli_cluster` when its anchor sheet's `StructureBag`
carries the three signals that distinguish a PLI table from a metadata
or reference sheet:

  1. at least one date cell  (any `DateStrip`)
  2. at least one numeric value cell  (any `IntStrip` or `FloatStrip`)
  3. either a key-value layout (any `KvBlock`) or a header band whose
     row contains at least one identifier label alias

Anything else is `other_sheets`. The binary distinction is intentional —
callers downstream branch only on this two-valued role.

`classify_cluster_role` mutates the cluster's `role` field and returns
the new value. `filter_pli_clusters` drops the `other_sheets` entries
once classification is complete.
"""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import StructureBag
from app.artifacts.workbook import ClusterRole, PliCluster
from app.specs import IDENTIFIER_SPECS


def classify_cluster_role(cluster: PliCluster,
                            canvas: GridCanvas,
                            bag: StructureBag) -> ClusterRole:
    """Decide the cluster's role from its anchor sheet's canvas + bag.

    Mutates `cluster.role` in place and returns the new value.
    """
    role: ClusterRole = "pli_cluster" if _looks_like_pli_table(canvas, bag) else "other_sheets"
    cluster.role = role
    return role


def filter_pli_clusters(clusters: list[PliCluster]) -> list[PliCluster]:
    """Return only the clusters whose role is `pli_cluster`."""
    return [c for c in clusters if c.role == "pli_cluster"]


def _looks_like_pli_table(canvas: GridCanvas, bag: StructureBag) -> bool:
    """Apply the three-signal rule."""
    if not bag.date_strips:
        return False
    if not (bag.int_strips or bag.float_strips):
        return False
    if bag.kv_blocks:
        return True
    return _header_band_carries_identifier_alias(canvas, bag)


def _header_band_carries_identifier_alias(canvas: GridCanvas, bag: StructureBag) -> bool:
    """True when at least one cell inside the header band matches an identifier spec alias."""
    if bag.header_band is None:
        return False
    rect = bag.header_band.rect
    aliases = _collected_aliases_lowercased()
    for r in range(rect.r0, rect.r1 + 1):
        for c in range(rect.c0, rect.c1 + 1):
            value = canvas.cell_values[r - 1][c - 1]
            if isinstance(value, str) and value.strip().lower() in aliases:
                return True
    return False


def _collected_aliases_lowercased() -> set[str]:
    """Union of every alias listed on every identifier spec, lowercased."""
    out: set[str] = set()
    for spec in IDENTIFIER_SPECS:
        for alias in spec.aliases:
            out.add(alias.lower())
    return out
