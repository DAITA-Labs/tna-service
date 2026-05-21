"""FieldNamer tuning knobs — including canonical allow-lists for validate_output."""
from __future__ import annotations

from pydantic import Field

from app.inferencing.tuning import AgentTuning


# Canonical names — keep in sync with app/prompts/field_namer.py
_PLI_FIELD_CANONICALS: list[str] = [
    "io_number", "style_code", "style_name", "color_code", "color_name",
    "fabric_code", "delivery_date", "quantity",
]

_METADATA_BOUND_CANONICALS: list[str] = [
    "order_receipt_date", "pps_completion", "sample_completion",
    "ex_factory_date", "buyer", "season", "factory", "article_no", "price",
    "balance_qty", "buyer_po_no", "fabric_quality", "cut_qty", "sewing_qty",
    "shipped_qty", "etd_ex_factory", "sample_dispatch",
]

_STAGE_CANONICALS: list[str] = [
    "fabric", "lab_dip_send", "lab_dip_approval", "fit_send", "fit_approval",
    "art_work_send", "art_work_approval", "in_house_fabric_send",
    "in_house_fabric_approval", "pre_production_send", "pre_production_approval",
    "first_pattern", "garment_pattern", "planned_completion_date",
    "size_set", "lot_card", "cutting", "feeding", "sewing", "sewing_start",
    "sewing_end", "final_inspection", "printing", "embroidery", "washing",
    "finishing", "packing", "ex_factory", "trims_inhouse",
]

_SUBFIELD_CANONICALS: list[str] = [
    "planned_date", "actual_date", "approval_date", "received_date",
    "approved_qty", "quantity", "remarks", "comments", "deviation_days",
]


class FieldNamerTuning(AgentTuning):
    """Per-agent tuning for FieldNamer."""

    # sample_rows inherited from AgentTuning (default 8) but FieldNamer's
    # build_input uses k=3 — override here so it's discoverable.
    pli_field_canonicals: list[str] = Field(default_factory=lambda: list(_PLI_FIELD_CANONICALS))
    metadata_bound_canonicals: list[str] = Field(default_factory=lambda: list(_METADATA_BOUND_CANONICALS))
    stage_canonicals: list[str] = Field(default_factory=lambda: list(_STAGE_CANONICALS))
    subfield_canonicals: list[str] = Field(default_factory=lambda: list(_SUBFIELD_CANONICALS))
    semantic_examples: list[dict] = Field(default_factory=list)
    anti_pattern_examples: list[dict] = Field(default_factory=list)
