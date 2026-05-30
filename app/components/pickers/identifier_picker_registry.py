"""Registry: canonical → (FieldSpec, strips_attr_name) for IdentifierPicker.

One row per identifier-shaped canonical. The `strips_attr_name` is the
attribute on `StructureBag` whose strip records confirm a column for
this canonical (e.g. `int_strips` for quantity, `date_strips` for
delivery_date).

PlanAssembler iterates this registry to build one `IdentifierPicker`
per canonical and assemble per-canonical scoreboards into the global
plan scoreboard. Adding a new identifier-shaped canonical = one line
here.
"""
from __future__ import annotations

from app.specs import (
    COLOR_CODE_SPEC,
    COLOR_NAME_SPEC,
    DELIVERY_DATE_SPEC,
    EX_FTY_DATE_SPEC,
    FABRIC_CODE_SPEC,
    FABRIC_NAME_SPEC,
    IO_NUMBER_SPEC,
    QUANTITY_SPEC,
    SHIPMENT_DATE_SPEC,
    STYLE_CODE_SPEC,
    STYLE_NAME_SPEC,
    FieldSpec,
)


# canonical → (spec, strips_attr_name on StructureBag)
IDENTIFIER_PICKER_CONFIGS: dict[str, tuple[FieldSpec, str]] = {
    IO_NUMBER_SPEC.canonical:      (IO_NUMBER_SPEC,      "same_length_strips"),
    QUANTITY_SPEC.canonical:       (QUANTITY_SPEC,       "int_strips"),
    STYLE_CODE_SPEC.canonical:     (STYLE_CODE_SPEC,     "same_length_strips"),
    COLOR_CODE_SPEC.canonical:     (COLOR_CODE_SPEC,     "same_length_strips"),
    FABRIC_CODE_SPEC.canonical:    (FABRIC_CODE_SPEC,    "same_length_strips"),
    STYLE_NAME_SPEC.canonical:     (STYLE_NAME_SPEC,     "long_text_strips"),
    COLOR_NAME_SPEC.canonical:     (COLOR_NAME_SPEC,     "long_text_strips"),
    FABRIC_NAME_SPEC.canonical:    (FABRIC_NAME_SPEC,    "long_text_strips"),
    DELIVERY_DATE_SPEC.canonical:  (DELIVERY_DATE_SPEC,  "date_strips"),
    SHIPMENT_DATE_SPEC.canonical:  (SHIPMENT_DATE_SPEC,  "date_strips"),
    EX_FTY_DATE_SPEC.canonical:    (EX_FTY_DATE_SPEC,    "date_strips"),
}
