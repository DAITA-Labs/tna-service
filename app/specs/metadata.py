"""Metadata field specs — Area.METADATA ADVISORY HINTS for known labels.

OPEN VOCABULARY DESIGN
======================
Metadata is GENUINELY OPEN. Any label-value pair found on the sheet that is
not one of the 9 identifier canonicals and not a stage becomes a
`MetadataEntry(key, value, source, canonical=None)`. The METADATA_SPECS
below are NOT a closed set — they are advisory hints that let us attach a
nice canonical name to common labels.

How the specs below are actually used:

1. SOFT MATCHING — when a metadata k:v is detected, the deterministic layer
   tries to match the raw label against each MetadataSpec's aliases. If a
   match fires, the entry ships with `canonical = <spec.canonical>`. If no
   match, the entry STILL SHIPS, with `canonical = None` and `key = <raw label>`.

2. PROMPT RENDERING — the MetadataKVJudge prompt receives these specs as
   reference for what known canonicals look like. The judge does NOT have
   to pick from the list; it may propose `canonical=None` for novel labels.

3. CONSUMER CONVENIENCE — downstream code looking for the buyer name can
   check `entry.canonical == "buyer"`. If buyer was not in the spec table
   (or the supplier used a novel label), the entry still exists; consumers
   fall back to scanning `entry.key`.

To ADD a new known canonical (purely optional improvement):
  1. Append a new FieldSpec below
  2. Add it to METADATA_SPECS at the bottom of the file
  3. The system already works without it — new labels ship verbatim
"""
from __future__ import annotations

from app.specs._base import FieldSpec, ValueConstraints
from app.specs.enums import Area, LabelMatchMode, ValueDtype, ValueDtypeMode, ValuePattern


BUYER_SPEC = FieldSpec(
    canonical="buyer",
    area=Area.METADATA,
    description="Buyer / customer name. Typically a company or brand.",
    aliases=("buyer", "customer", "buyer name", "client", "brand"),
    patterns=(
        "labels like 'Buyer', 'Customer', 'Brand'",
        "value is a name (string), often appearing once in metadata block",
    ),
    anti_patterns=("do NOT match 'Buyer PO' — that is buyer_po_no",),
    examples=("Buyer", "Customer", "Brand"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.STR,
    value_dtype_mode=ValueDtypeMode.MEDIUM,
    value_constraints=ValueConstraints(allowed_patterns=(ValuePattern.NAME_TEXT,)),
)


SEASON_SPEC = FieldSpec(
    canonical="season",
    area=Area.METADATA,
    description="Season identifier (e.g. SS-26, AW26, FW26, Spring 2026).",
    aliases=("season", "ct season", "season name", "sea"),
    patterns=(
        "labels like 'Season', 'CT Season'",
        "values like 'SS-26', 'AW26', 'FW26', 'Spring 2026'",
    ),
    anti_patterns=(),
    examples=("Season", "CT Season"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.STR,
    value_dtype_mode=ValueDtypeMode.SOFT,
    value_constraints=ValueConstraints(max_len=20),
)


FACTORY_SPEC = FieldSpec(
    canonical="factory",
    area=Area.METADATA,
    description="Factory name / unit where the PLI is being produced.",
    aliases=("factory", "factory name", "unit", "production unit", "plant"),
    patterns=("labels like 'Factory', 'Unit'",),
    anti_patterns=(),
    examples=("Factory", "Unit", "Plant"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.STR,
    value_dtype_mode=ValueDtypeMode.MEDIUM,
)


# NOTE: BUYER_PO_NO_SPEC was REMOVED. The buyer's PO number is now
# absorbed as an alias of io_number — see IO_NUMBER_SPEC in identifiers.py.
# Rationale: when a supplier uses "Buyer PO No" as the per-PLI identifier
# on a sheet, it IS the io_number for that sheet (functional role, not
# specific label). A separate metadata.buyer_po_no canonical only adds
# routing ambiguity. If a sheet has BOTH an internal-order column AND a
# distinct PO column, the internal-order wins via alias-priority and the
# PO column will surface as a raw metadata entry with canonical=None.


# NOTE: EX_FACTORY_DATE_SPEC was REMOVED from metadata. The "ex-factory
# date" concept is now a first-class IDENTIFIER as `ex_fty_date` — see
# EX_FTY_DATE_SPEC in identifiers.py. Rationale: factory-exit date is part
# of the PLI's identity timeline (one of three required date anchors), not
# loose metadata. Stage-wins rule still applies: if the cell belongs to an
# 'Ex Factory Shipment' STAGE band, the stage captures it, not the
# identifier.


ORDER_RECEIPT_DATE_SPEC = FieldSpec(
    canonical="order_receipt_date",
    area=Area.METADATA,
    description="Date the order was received from the buyer.",
    aliases=(
        "order receipt date", "order receipt", "order date", "or date",
        "receipt date", "order received",
    ),
    patterns=("labels like 'Order Receipt Date', 'Order Date'",),
    anti_patterns=(
        "do NOT match 'Delivery Date' — that is identifier.delivery_date",
    ),
    examples=("Order Receipt Date", "Order Date"),
    label_match_mode=LabelMatchMode.SOFT,
    value_dtype=ValueDtype.DATE,
    value_dtype_mode=ValueDtypeMode.HARD,
    value_constraints=ValueConstraints(allowed_patterns=(ValuePattern.DATE,)),
)


# =============================================================================
# Registry — known metadata specs (extensible)
# =============================================================================

METADATA_SPECS: tuple[FieldSpec, ...] = (
    BUYER_SPEC,
    SEASON_SPEC,
    FACTORY_SPEC,
    ORDER_RECEIPT_DATE_SPEC,
)

METADATA_CANONICALS: tuple[str, ...] = tuple(s.canonical for s in METADATA_SPECS)


def get_metadata_spec(canonical: str) -> FieldSpec:
    for spec in METADATA_SPECS:
        if spec.canonical == canonical:
            return spec
    raise KeyError(f"unknown metadata canonical: {canonical!r}")
