"""Identifier field specs — Area.IDENTIFIERS.

9 canonical identifier fields. io_number + quantity are mandatory and double
as bootstrap signals for inferring pli_mode.

To add a new identifier:
  1. Append a new FieldSpec below
  2. Add it to IDENTIFIER_SPECS at the bottom of the file
  3. (No other file to update — specs are read by both matcher AND prompts)
"""
from __future__ import annotations

from app.specs._base import FieldSpec, ValueConstraints
from app.specs.enums import Area, LabelMatchMode, ValueDtype, ValueDtypeMode, ValuePattern


# =============================================================================
# io_number — MANDATORY, bootstrap signal for pli_mode
# =============================================================================

IO_NUMBER_SPEC = FieldSpec(
    canonical="io_number",
    area=Area.IDENTIFIERS,
    description=(
        "The per-PLI order identifier — a FUNCTIONAL ROLE, not a specific "
        "label. Whatever column the supplier uses to identify each PLI on "
        "this sheet IS io_number, regardless of what the supplier calls it: "
        "'IO No', 'Internal Order', 'Buyer PO No', 'PO No', 'Job No', etc. "
        "If multiple identifier columns exist (e.g. an internal order AND a "
        "buyer PO), prefer the more specific one (internal-order aliases "
        "earlier in the list outrank PO aliases).\n\n"
        "Location pattern hints at pli_mode:\n"
        "  column-with-many-values            = ROW_PER_PLI\n"
        "  single label-value cell            = SHEET_IS_PLI\n"
        "  repeated label-value across blocks = SECTION_PER_PLI"
    ),
    aliases=(
        # Internal-order family (highest priority — supplier's own ID)
        "io", "io no", "io #", "io number", "io.no", "ionumber", "ion",
        "internal order", "internal order no", "io ref", "io reference",
        "internal ref", "tn no",
        # Job/work-order family (supplier's job identifier)
        "job no", "job #", "job number", "job ref",
        # Buyer PO family (used as the per-PLI ID when no internal io exists)
        "buyer po no", "buyer po #", "buyer po", "buyer po number",
        "po no", "po #", "po number", "po.no", "purchase order",
        "purchase order no", "buyer ref", "buyer reference",
    ),
    patterns=(
        "labels like 'IO No', 'IO #', 'Internal Order', 'Job No'",
        "labels like 'PO No', 'Buyer PO' when no separate internal-order column exists",
        "values are alphanumeric tokens (any reasonable length)",
        "value column has many distinct values (one per PLI row in ROW_PER_PLI)",
        "value may be present once in a metadata block (SHEET_IS_PLI)",
    ),
    anti_patterns=(
        "DO NOT match 'Order Qty' or 'Qty' — those are quantity",
        "DO NOT require numeric values — io_number can be any string",
        "DO NOT match style codes like 'Style No' — those are style_code",
        "If BOTH an internal-order column AND a buyer-PO column exist, "
        "the internal-order column wins; the PO column may still be "
        "captured as a separate metadata entry.",
    ),
    examples=(
        "IO No", "IO #", "Internal Order", "Job No",
        "Buyer PO No", "PO No", "Buyer PO",
    ),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.ANY,
    value_dtype_mode=ValueDtypeMode.SOFT,
    value_constraints=ValueConstraints(
        max_len=30,
    ),
    mandatory=True,
)


# =============================================================================
# quantity — MANDATORY, numeric, helps identify table shape
# =============================================================================

QUANTITY_SPEC = FieldSpec(
    canonical="quantity",
    area=Area.IDENTIFIERS,
    description=(
        "Total order quantity for the PLI. Always numeric. Can be a single "
        "total OR a sized breakdown (XS/S/M/L) summing to total. Distinct "
        "from sized-breakdown size columns (which hold per-size counts and "
        "are typically int_small)."
    ),
    aliases=(
        # MOST SPECIFIC FIRST. Spec-alias-position drives single-column
        # arbitration; bare "qty" is the most ambiguous and must be LAST,
        # so a column header "Order Qty" outranks a sibling subheader "Qty".
        "order quantity", "total quantity", "order qty", "total qty",
        "qty ordered", "ord qty", "quantity", "qty.", "pcs", "pieces",
        "qty",
    ),
    patterns=(
        "labels like 'Order Qty', 'Total Qty', 'Pcs', 'Quantity'",
        "values are positive ints in range 1..100000",
        "value column has many distinct values (one per PLI in ROW_PER_PLI)",
    ),
    anti_patterns=(
        "DO NOT match 'Qty Shipped', 'Qty Cut', 'Qty Sewn' — those are stage_metadata",
        "DO NOT match per-size columns labeled 'XS', 'S', 'M' — those are size breakdown",
        "DO NOT match very small ints (0-10) — those are likely sizes, not order qty",
    ),
    examples=("Order Qty", "Total Qty", "Qty", "Pcs", "Quantity", "Qty Ordered"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.INT,
    value_dtype_mode=ValueDtypeMode.MEDIUM,
    value_constraints=ValueConstraints(
        min=1,
        max=100000,
        allowed_patterns=(ValuePattern.INT_LARGE, ValuePattern.INT_MEDIUM),
    ),
    mandatory=True,
)


# =============================================================================
# style_code — compact alphanumeric style identifier
# =============================================================================

STYLE_CODE_SPEC = FieldSpec(
    canonical="style_code",
    area=Area.IDENTIFIERS,
    description=(
        "The PRIMARY style identifier slot. When a sheet has a SINGLE "
        "style column (whatever its label — 'Style', 'Style No', 'Article'), "
        "the value lands here regardless of length or format (a compound "
        "code like '890162 TAVIRA_2 522148' is fine).\n\n"
        "`style_name` is a SECONDARY slot — used ONLY when the sheet has "
        "BOTH a code-leaning column AND a descriptive-phrase column. The "
        "*_code > *_name priority rule: single column → always *_code."
    ),
    aliases=(
        "style", "style no", "style #", "style code", "style number",
        "sty", "sty no", "style ref", "art no", "article no", "article #",
    ),
    patterns=(
        "labels like 'Style #', 'Style Code', 'Article No', 'Sty No', 'Style'",
        "value may be short or long; structured or descriptive — no constraint",
    ),
    anti_patterns=(
        "DO NOT match this spec WHEN the same sheet has BOTH a code column AND a "
        "name column. In that case the descriptive column goes to style_name.",
    ),
    examples=("Style #", "Style Code", "Art No", "Style", "Sty No", "Style Number"),
    label_match_mode=LabelMatchMode.SOFT,
    value_dtype=ValueDtype.ANY,
    value_dtype_mode=ValueDtypeMode.SOFT,
    value_constraints=ValueConstraints(),
)


# =============================================================================
# style_name — descriptive style phrase
# =============================================================================

STYLE_NAME_SPEC = FieldSpec(
    canonical="style_name",
    area=Area.IDENTIFIERS,
    description=(
        "SECONDARY style slot — only used when the sheet has BOTH a "
        "code-leaning column AND a separate descriptive-phrase column. "
        "Examples: a sheet with 'Style #' (→ style_code) AND 'Style "
        "Description' (→ style_name). When a sheet has only ONE style "
        "column, the value goes to style_code (priority rule), not here."
    ),
    aliases=(
        "style name", "style description", "design name", "product name",
        "garment name", "item name", "description", "garment description",
    ),
    patterns=(
        "labels explicitly indicating a NAME/DESCRIPTION variant",
        "ONLY meaningful when a separate style_code column also exists on the sheet",
    ),
    anti_patterns=(
        "DO NOT match when this is the only style column on the sheet — that "
        "value goes to style_code under the priority rule.",
    ),
    examples=("Style Name", "Style Description", "Description", "Design Name"),
    label_match_mode=LabelMatchMode.SOFT,
    value_dtype=ValueDtype.STR,
    value_dtype_mode=ValueDtypeMode.SOFT,
    value_constraints=ValueConstraints(),
)


# =============================================================================
# color_code — short color code (vs color_name which is text)
# =============================================================================

COLOR_CODE_SPEC = FieldSpec(
    canonical="color_code",
    area=Area.IDENTIFIERS,
    description=(
        "The PRIMARY color identifier slot. When a sheet has a SINGLE "
        "color column (whatever its label — 'Color', 'Color Code', "
        "'Colour'), the value lands here regardless of whether it looks "
        "like a numeric code (6602) or a descriptive name ('MAGENTA').\n\n"
        "`color_name` is a SECONDARY slot — used ONLY when the sheet has "
        "BOTH a code-leaning column AND a separate descriptive-name column. "
        "*_code > *_name priority: single column → always *_code."
    ),
    aliases=(
        "color", "colour", "color code", "color #", "color no",
        "col", "col code", "colour code", "clr",
    ),
    patterns=(
        "labels like 'Color', 'Color Code', 'Colour Code', 'Col'",
        "value may be short numeric (6602), short alnum (RED-01), or descriptive ('MAGENTA')",
    ),
    anti_patterns=(
        "DO NOT match this spec WHEN the same sheet has BOTH a code column AND a name "
        "column. In that case the descriptive column goes to color_name.",
    ),
    examples=("Color", "Color Code", "Colour Code", "Col"),
    label_match_mode=LabelMatchMode.SOFT,
    value_dtype=ValueDtype.ANY,
    value_dtype_mode=ValueDtypeMode.SOFT,
    value_constraints=ValueConstraints(),
)


# =============================================================================
# color_name — descriptive color (SECONDARY slot)
# =============================================================================

COLOR_NAME_SPEC = FieldSpec(
    canonical="color_name",
    area=Area.IDENTIFIERS,
    description=(
        "SECONDARY color slot — only used when the sheet has BOTH a "
        "code-leaning color column AND a separate descriptive-name column. "
        "Example: a sheet with 'Color Code' (→ color_code) AND 'Color Name' "
        "(→ color_name). When a sheet has only ONE color column, that value "
        "goes to color_code (priority rule), not here."
    ),
    aliases=(
        "color name", "colour name", "color description",
        "clr name", "colour description",
    ),
    patterns=(
        "labels explicitly indicating a NAME/DESCRIPTION variant",
        "ONLY meaningful when a separate color_code column also exists on the sheet",
    ),
    anti_patterns=(
        "DO NOT match when this is the only color column on the sheet — that "
        "value goes to color_code under the priority rule.",
    ),
    examples=("Color Name", "Colour Name", "Colour Description"),
    label_match_mode=LabelMatchMode.SOFT,
    value_dtype=ValueDtype.STR,
    value_dtype_mode=ValueDtypeMode.SOFT,
    value_constraints=ValueConstraints(),
)


# =============================================================================
# fabric_code — short fabric code
# =============================================================================

FABRIC_CODE_SPEC = FieldSpec(
    canonical="fabric_code",
    area=Area.IDENTIFIERS,
    description=(
        "The PRIMARY fabric identifier slot. When a sheet has a SINGLE "
        "fabric column (whatever its label — 'Fabric', 'Fabric Code', "
        "'Fabric Quality', 'Composition'), the value lands here regardless "
        "of length or format. A long composition string like '2X2 RIB/100% "
        "COTTON/34S/YARN DYED' is a valid fabric_code under this rule.\n\n"
        "`fabric_name` is a SECONDARY slot — used ONLY when the sheet has "
        "BOTH a code-leaning column AND a separate name/composition column. "
        "*_code > *_name priority: single column → always *_code."
    ),
    aliases=(
        "fabric", "fabric code", "fabric #", "fabric no",
        "fab code", "fbc", "fab #", "fbr code",
        # Quality / composition labels also route to *_code when they are
        # the ONLY fabric column on the sheet
        "fabric quality", "fabric composition", "fabric description",
        "composition", "quality", "fbc name", "fbr name",
    ),
    patterns=(
        "labels like 'Fabric', 'Fabric Code', 'Fabric Quality', 'Composition'",
        "value may be a short code (CTN-01) or a long composition string",
    ),
    anti_patterns=(
        "DO NOT match this spec WHEN the same sheet has BOTH a code column AND "
        "a separate descriptive column. In that case the descriptive column "
        "goes to fabric_name.",
    ),
    examples=("Fabric", "Fabric Code", "Fab Code", "Fabric Quality", "Composition"),
    label_match_mode=LabelMatchMode.SOFT,
    value_dtype=ValueDtype.ANY,
    value_dtype_mode=ValueDtypeMode.SOFT,
    value_constraints=ValueConstraints(),
)


# =============================================================================
# fabric_name — SECONDARY fabric slot (only when both code and name exist)
# =============================================================================

FABRIC_NAME_SPEC = FieldSpec(
    canonical="fabric_name",
    area=Area.IDENTIFIERS,
    description=(
        "SECONDARY fabric slot — only used when the sheet has BOTH a "
        "code-leaning fabric column AND a separate name/composition column. "
        "Example: a sheet with 'Fabric Code' (→ fabric_code) AND 'Fabric "
        "Quality' (→ fabric_name). When a sheet has only ONE fabric column, "
        "the value goes to fabric_code (priority rule), not here."
    ),
    aliases=(
        "fabric name", "fabric quality (name)", "fabric description",
        # Note: many labels here also appear in FABRIC_CODE_SPEC. fabric_name
        # only wins when there's ALREADY a fabric_code column matched elsewhere.
    ),
    patterns=(
        "labels explicitly indicating a NAME/DESCRIPTION variant alongside a code column",
        "ONLY meaningful when a separate fabric_code column also exists on the sheet",
    ),
    anti_patterns=(
        "DO NOT match when this is the only fabric column on the sheet — that "
        "value goes to fabric_code under the priority rule.",
    ),
    examples=("Fabric Name", "Fabric Description"),
    label_match_mode=LabelMatchMode.SOFT,
    value_dtype=ValueDtype.STR,
    value_dtype_mode=ValueDtypeMode.SOFT,
    value_constraints=ValueConstraints(),
)


# =============================================================================
# delivery_date — date the PLI is due to be delivered
# =============================================================================

# =============================================================================
# THREE DATE IDENTIFIERS — semantically distinct
# =============================================================================
#
# Together these capture the supply-chain timeline:
#
#     ex_fty_date   →   shipment_date   →   delivery_date
#     (leaves factory)   (in transit)        (received by buyer)
#
# A PLI MUST have at least one of these three populated (hard rule).
# Different supplier templates surface different subsets:
#   - many use only `ex_fty_date` (e.g. "Etd Ex factory as per P.O")
#   - some use only `delivery_date` (e.g. "Delivery Date", "ETA")
#   - some use `shipment_date` for transport coordination
#
# Stage-wins disambiguation: if a date cell could be EITHER a stage's
# planned_date OR one of these identifiers, the STAGE wins (the cell is
# consumed by the stage band, not by the identifier section).
#
# =============================================================================

DELIVERY_DATE_SPEC = FieldSpec(
    canonical="delivery_date",
    area=Area.IDENTIFIERS,
    description=(
        "Date the PLI is delivered TO THE BUYER (arrival at buyer's end). "
        "Distinct from ex_fty_date (when goods leave the factory) and "
        "shipment_date (when goods are in transit). Use this for buyer-side "
        "milestones — 'Delivery Date', 'ETA' (Estimated Time of Arrival), "
        "'In-store date'."
    ),
    aliases=(
        "delivery", "delivery date", "del date", "del.date",
        "eta", "arrival", "arrival date",
        "buyer delivery", "buyer delivery date",
        "in-store", "in store", "in-store date",
        "delivery deadline", "due date",
    ),
    patterns=(
        "labels like 'Delivery Date', 'ETA', 'In-Store', 'Arrival'",
        "values are date-typed",
        "semantically: date GOODS REACH the buyer",
    ),
    anti_patterns=(
        "DO NOT match stage band date columns (those are stage plan/actual dates)",
        "DO NOT match 'Ex Factory' or 'Ex-Factory' — that is ex_fty_date",
        "DO NOT match 'Shipment' or 'Ship Date' — that is shipment_date",
        "DO NOT match 'Order Receipt Date' or 'Order Date' — those are metadata",
    ),
    examples=("Delivery Date", "ETA", "Arrival Date", "In-Store Date", "Del Date"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.DATE,
    value_dtype_mode=ValueDtypeMode.HARD,
    value_constraints=ValueConstraints(
        allowed_patterns=(ValuePattern.DATE,),
    ),
)


# =============================================================================
# shipment_date — transport to buyer / manufacture
# =============================================================================

SHIPMENT_DATE_SPEC = FieldSpec(
    canonical="shipment_date",
    area=Area.IDENTIFIERS,
    description=(
        "Date the PLI is in transit — being shipped to the buyer or "
        "manufacturer. Distinct from ex_fty_date (leaves factory) and "
        "delivery_date (received). Use this for transport-coordination "
        "milestones — 'Ship Date', 'Dispatch Date', 'Transport Date'."
    ),
    aliases=(
        "shipment", "shipment date", "ship", "ship date", "ship by",
        "shipping", "shipping date",
        "dispatch", "dispatch date",
        "transport", "transport date",
        "in transit", "in-transit", "in-transit date",
        "courier date", "freight date",
        "ex con", "ex-con", "ex country", "ex-country", "ex country date",
    ),
    patterns=(
        "labels like 'Ship Date', 'Shipment Date', 'Dispatch Date'",
        "values are date-typed",
        "semantically: date goods are IN TRANSIT to buyer / next stage",
    ),
    anti_patterns=(
        "DO NOT match stage band date columns",
        "DO NOT match 'Ex Factory' / 'Ex-Factory' — that is ex_fty_date",
        "DO NOT match 'Delivery' / 'ETA' / 'Arrival' — that is delivery_date",
        "DO NOT match 'Ex Factory Shipment' STAGE columns (stage-wins rule)",
    ),
    examples=("Shipment Date", "Ship Date", "Dispatch Date", "Transport Date"),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.DATE,
    value_dtype_mode=ValueDtypeMode.HARD,
    value_constraints=ValueConstraints(
        allowed_patterns=(ValuePattern.DATE,),
    ),
)


# =============================================================================
# ex_fty_date — date the order leaves the factory
# =============================================================================

EX_FTY_DATE_SPEC = FieldSpec(
    canonical="ex_fty_date",
    area=Area.IDENTIFIERS,
    description=(
        "Date the PLI leaves the factory (out the door). Distinct from "
        "shipment_date (in transit) and delivery_date (received). Use this "
        "for factory-exit milestones — 'Ex Factory', 'Ex-Factory Date', "
        "'ETD Ex Factory', 'Out of Factory'.\n\n"
        "STAGE-WINS RULE: if a sheet has an 'Ex Factory Shipment' STAGE "
        "column (with planned_date cells per PLI), that data is captured "
        "as the stage — NOT as ex_fty_date identifier. Use ex_fty_date "
        "only for sheet-level / PLI-level cells that aren't part of a "
        "stage band."
    ),
    aliases=(
        "ex factory", "ex-factory", "ex factory date", "ex-factory date",
        "ex fty", "exf", "ex.factory", "exfactory",
        "etd ex factory", "etd ex-factory", "etd ex fty", "etd exf",
        "factory exit", "out of factory", "exit factory",
        "ex fac", "ex-fac", "ex fac date", "ex-fac date", "ex fty date",
    ),
    patterns=(
        "labels like 'Ex Factory Date', 'Etd Ex factory as per P.O', 'EXF'",
        "values are date-typed",
        "semantically: date goods LEAVE the factory",
    ),
    anti_patterns=(
        "DO NOT match 'Delivery' / 'ETA' / 'Arrival' — that is delivery_date",
        "DO NOT match 'Ship Date' / 'Shipment' alone — that is shipment_date",
        "DO NOT match if the cell belongs to an 'Ex Factory Shipment' STAGE "
        "(stage-wins rule — the stage band's plan_date column takes precedence)",
    ),
    examples=(
        "Ex Factory", "Ex-Factory Date", "Etd Ex factory as per P.O",
        "EXF Date", "ETD Ex Factory",
    ),
    label_match_mode=LabelMatchMode.MEDIUM,
    value_dtype=ValueDtype.DATE,
    value_dtype_mode=ValueDtypeMode.HARD,
    value_constraints=ValueConstraints(
        allowed_patterns=(ValuePattern.DATE,),
    ),
)


# =============================================================================
# Registry — every identifier spec
# =============================================================================

# Order matters: *_code specs come BEFORE *_name specs so that when a
# label like "Color" / "Fabric" / "Style" could match either, the *_code
# spec is evaluated first and wins via cross-spec dedupe (hard principle:
# *_code > *_name). The matcher relies on this ordering.
#
# Date identifiers are listed after non-date identifiers; their ordering
# among themselves doesn't matter (they have disjoint vocab).
IDENTIFIER_SPECS: tuple[FieldSpec, ...] = (
    IO_NUMBER_SPEC,
    QUANTITY_SPEC,
    STYLE_CODE_SPEC,
    STYLE_NAME_SPEC,
    COLOR_CODE_SPEC,
    COLOR_NAME_SPEC,
    FABRIC_CODE_SPEC,
    FABRIC_NAME_SPEC,
    DELIVERY_DATE_SPEC,
    SHIPMENT_DATE_SPEC,
    EX_FTY_DATE_SPEC,
)

IDENTIFIER_CANONICALS: tuple[str, ...] = tuple(s.canonical for s in IDENTIFIER_SPECS)
MANDATORY_IDENTIFIERS: tuple[str, ...] = tuple(s.canonical for s in IDENTIFIER_SPECS if s.mandatory)

# Hard rule: every PLI must have at least ONE of these three populated.
# Enforced post-extraction (validator or phase judge). At least one date
# anchor is required for downstream scheduling/tracking.
DATE_IDENTIFIERS_AT_LEAST_ONE: tuple[str, ...] = (
    "delivery_date",
    "shipment_date",
    "ex_fty_date",
)


def get_identifier_spec(canonical: str) -> FieldSpec:
    """Lookup helper."""
    for spec in IDENTIFIER_SPECS:
        if spec.canonical == canonical:
            return spec
    raise KeyError(f"unknown identifier canonical: {canonical!r}")
