"""MetadataFindingJudge I/O schemas.

The judge reviews one `MetadataEntry` whose `canonical` is `None` — a
k:v label the alias matcher couldn't catalog-resolve. Per the
metadata-is-open principle, novel keys are legitimate: the judge
decides whether to map a label onto a known canonical hint, drop the
entry, or keep it open-vocab.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.artifacts.agent_io import AgentOutput
from app.specs.schemas import MetadataEntry


class MetadataFindingForJudge(BaseModel):
    """Inputs to the MetadataFindingJudge — one open-vocab metadata entry + context."""

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    metadata:         MetadataEntry
    metadata_catalog: str
    sheet_excerpt:    str
    cluster_context:  str = ""


class MetadataVerdict(AgentOutput):
    """The judge's decision for one metadata entry."""

    decision:               Literal["keep", "drop", "rewrite"]
    alternative_canonical:  str | None = None
    reason:                 str = Field(min_length=1, max_length=500)
    confidence:             Literal["high", "medium", "low"]
