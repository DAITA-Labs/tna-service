"""ClusterRole — semantic role of a workbook cluster after classification."""
from __future__ import annotations

from enum import Enum


class ClusterRole(str, Enum):
    PLI_CLUSTER    = "pli_cluster"
    METADATA_ONLY  = "metadata_only"
    SUMMARY        = "summary"
    OTHER          = "other"
