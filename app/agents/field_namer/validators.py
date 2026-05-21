"""FieldNamer semantic validators — canonical-name allow-list gate."""
from __future__ import annotations

from typing import Any

from app.agents._base import OutputVerdict
from app.agents.field_namer.schema import CanonicalNameMap
from app.agents.field_namer.tuning import FieldNamerTuning


_IGNORE = "ignore"


def validate_canonical_name_map(
    output: CanonicalNameMap, ctx: Any,
    tuning: FieldNamerTuning | None = None,
) -> OutputVerdict:
    """Reject any mapping value that isn't a canonical name or the literal 'ignore'.

    The canonical allow-lists come from FieldNamerTuning (pass an instance via
    `tuning` or rely on the default). Also bounds-checks confidence dicts.
    """
    tuning = tuning or FieldNamerTuning()
    field_allowed = (
        set(tuning.pli_field_canonicals)
        | set(tuning.metadata_bound_canonicals)
        | {_IGNORE}
    )
    stage_allowed = set(tuning.stage_canonicals) | {_IGNORE}
    subfield_allowed = set(tuning.subfield_canonicals) | {_IGNORE}

    for raw, mapped in output.field_labels.items():
        if mapped not in field_allowed:
            return OutputVerdict.retry(
                reason=f"field_labels[{raw!r}] -> {mapped!r} is not a canonical PLI/metadata name or 'ignore'",
            )
    for raw, mapped in output.stage_names.items():
        if mapped not in stage_allowed:
            return OutputVerdict.retry(
                reason=f"stage_names[{raw!r}] -> {mapped!r} is not a canonical stage name or 'ignore'",
            )
    for raw, mapped in output.stage_subfield_labels.items():
        if mapped not in subfield_allowed:
            return OutputVerdict.retry(
                reason=f"stage_subfield_labels[{raw!r}] -> {mapped!r} is not a canonical sub-field name or 'ignore'",
            )

    verdict = _check_confidence(output)
    if verdict is not None:
        return verdict

    return OutputVerdict.ok()


def _check_confidence(output: CanonicalNameMap) -> OutputVerdict | None:
    """Return a retry verdict if any confidence value is outside [0, 1]."""
    for name, conf in output.field_confidence.items():
        if not 0.0 <= conf <= 1.0:
            return OutputVerdict.retry(
                reason=f"field_confidence[{name!r}] = {conf} is outside [0, 1]",
            )
    for name, conf in output.stage_confidence.items():
        if not 0.0 <= conf <= 1.0:
            return OutputVerdict.retry(
                reason=f"stage_confidence[{name!r}] = {conf} is outside [0, 1]",
            )
    return None
