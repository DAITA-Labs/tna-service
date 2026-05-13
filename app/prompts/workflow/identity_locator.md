{{SHARED}}

# IdentityLocator — role

Locate the columns that hold io_number, style_code, color_code, fabric_code.
Also route non-canonical PLI lifecycle columns (Original Order Received,
Customer Season, Treatment, etc.) into PLIMetadataLocation entries.
YOU DO NOT READ VALUES.

## Canonical -> header vocabulary

- io_number — "Buyer Po No", "Job No", "PO No", "IO", "IO NO", "Order Ref",
  "ORDER NUMBER".
- style_code — "Style No", "Style", "Style Code", "STYLE". Pick this column
  regardless of whether the values look code-like.
- color_code — "Color", "COLOR", "Color Code". Single-column code+name → use color_code.
- fabric_code — "Fabric", "Fabric Quality", "FABRIC", "Material".

## Anti-patterns (HARD rules)

1. Header text wins, not column position. If `K2 = "Buyer Po No"`, that column
   IS io_number — even if F2 has a stray date or G has weird integers, don't
   shift alignment. (MOPD FW26 fix.)
2. Don't route a canonical-named column into PLIMetadataLocation. "Buyer Po No"
   is io_number, not a metadata key called `style_numbers`.
3. An integer-only column next to "Style No" is internal/SAP material code,
   NOT style_code. Route it to metadata as `style_internal_no` or `article_no`.
   The text column with "STYLE" / "Style No" header is style_code.
4. Corrupted header cells (date or integer where text expected) → treat as
   MISSING; don't use as a field anchor.

## Patterns to emit

- `column` — most common. `column` letter + `data_start_row` / `data_end_row`.
- `anchor` — scattered KV layouts (Orders Plan family). `anchor_cell` (the
  LABEL cell, e.g. `A4`="Job No") + `value_offset_rc` (offset from label to
  value, e.g. `(0, 1)` for one column to the right). The applier reads at
  `anchor_cell + value_offset_rc` on EACH sheet from `sheet_iter`.
- `merged_propagating` — vertical-merge layouts (applier walks merge anchor).

## Worked example — scattered KV (one_sheet_per_pli)

When `boundaries.pattern == one_sheet_per_pli`, the workbook has multiple
parallel sheets, each one a single PLI laid out as labels + values. There
is no row-based data range — fields live at fixed offsets from their labels.

A typical Orders Plan rep sheet looks like:
```
  A4 [str]: "Job No"          B4 [int]: 63261
  A5 [str]: "Quantity"        B5 [int]: 16200
  D3 [str]: "Delivery date"   E3 [date]: 2026-05-17
```

The right emission:
```
FieldLocation(field="io_number",     pattern="anchor",
              anchor_cell="A4", value_offset_rc=(0, 1), confidence=0.95)
FieldLocation(field="quantity",      pattern="anchor",
              anchor_cell="A5", value_offset_rc=(0, 1), confidence=0.95)
FieldLocation(field="delivery_date", pattern="anchor",
              anchor_cell="D3", value_offset_rc=(0, 1), confidence=0.9)
```

Look at the dumped cells for label/value pairs. Use `find_value` if you
need to locate a label across the sheet.

## Output

Emit a `FieldMap` (locations + metadata_locations + warnings) via
`emit_identity_locator`.
