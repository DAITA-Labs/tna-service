"""Shared prompt header — glossary + faithful-extraction + output-discipline."""
from __future__ import annotations

SHARED: str = """# Glossary

- **TNA** — Time and Action: production schedule with planned dates + qty per stage.
- **PLI** — Production Line Item: one row in a TNA (unique style + color + fabric).
- **IO Number** — Internal Order number. One TNA can have multiple PLI rows.
- **Stage** — Production milestone (e.g. Cutting, Sewing, Inspection) with a planned date.

# Faithful extraction principles

- TNA is source of truth. Do not split cells across multiple fields.
- If a cell holds combined "code + name", route to the *_code variant.
- "Original Order Received", "Factory Confirmed", "Etd Ex factory as per P.O" are
  lifecycle / PO fields — NOT stages.
- Quantity columns (Cut Qty, Sewing Qty, Color Qty, Shipped Qty) are NOT stages.
- A stage is a phase of manufacturing where physical work happens, not just any
  cell that holds a date.

# Output discipline

- Match canonical fields by HEADER TEXT, not column position.
- Treat a stray date or integer in a header cell as a MISSING header — don't
  use it as a field anchor.
- For single-column code+name content, always use *_code.
"""
