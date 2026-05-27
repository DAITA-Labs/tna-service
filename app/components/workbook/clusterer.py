"""Clusterer — group sheets into `PliCluster`s by signature similarity.

`cluster_sheets(signatures)` runs a union-find pass over all pairs of
signatures and merges any two sheets whose `score_signatures` is at or
above `DEFAULT_THRESHOLD` (0.8 by design). Each connected component
becomes one `PliCluster` with a stable `c0`, `c1`, ... id assigned in
discovery order.

Sheets that share no high-similarity neighbour become singleton
clusters — the role classifier later decides whether they belong to
`pli_cluster` or `other_sheets`.
"""
from __future__ import annotations

from haystack import component

from app.artifacts.workbook import PliCluster, SheetSignature
from app.components._base import Component
from app.components.workbook.signature import score_signatures


DEFAULT_THRESHOLD = 0.8


def cluster_sheets(signatures: list[SheetSignature],
                     threshold: float = DEFAULT_THRESHOLD) -> list[PliCluster]:
    """Union-find grouping of sheets whose pairwise similarity ≥ `threshold`."""
    n = len(signatures)
    if n == 0:
        return []

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if score_signatures(signatures[i], signatures[j]) >= threshold:
                union(i, j)

    # Assemble clusters in discovery order — the order each root first appears.
    root_to_cluster: dict[int, PliCluster] = {}
    cluster_order: list[int] = []
    for idx, sig in enumerate(signatures):
        root = find(idx)
        if root not in root_to_cluster:
            cluster_id = f"c{len(cluster_order)}"
            root_to_cluster[root] = PliCluster(cluster_id=cluster_id, sheet_names=[])
            cluster_order.append(root)
        root_to_cluster[root].sheet_names.append(sig.sheet_name)

    return [root_to_cluster[root] for root in cluster_order]


@component
class SheetClusterer(Component):
    """Haystack wrapper around `cluster_sheets`.

    Inputs:
        signatures — list[SheetSignature] from `WorkbookProfiler`
        threshold  — optional override of the 0.8 default

    Outputs:
        clusters — list[PliCluster] in discovery order
    """

    def __init__(self, threshold: float = DEFAULT_THRESHOLD) -> None:
        Component.__init__(self)
        self._threshold = threshold

    @component.output_types(clusters=list[PliCluster])
    def run(self, signatures: list[SheetSignature]) -> dict:
        clusters = cluster_sheets(signatures, threshold=self._threshold)
        return {"clusters": clusters}
