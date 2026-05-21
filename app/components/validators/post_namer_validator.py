"""PostNamerValidator — pipeline component that enforces every detected label is mapped."""
from __future__ import annotations

from haystack import component

from app.components._base import Component
from app.components.validators.post_namer_canonical import validate_post_namer
from app.core.log_capture import log_artifact
from app.models.artifacts import CanonicalNameMap, SheetPlan, ValidationFinding


@component
class PostNamerValidator(Component):
    """Pipeline component: enforces every detected label is mapped or 'ignore'."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(name_map=CanonicalNameMap, findings=list[ValidationFinding])
    def run(self, plan: SheetPlan, name_map: CanonicalNameMap) -> dict:
        """Return the name_map and any labels silently dropped by FieldNamer."""
        findings = validate_post_namer(plan, name_map)
        log_artifact("name_map.snapshot_after_namer", payload=name_map.model_dump())
        return {"name_map": name_map, "findings": findings}
