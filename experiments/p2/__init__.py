"""P2 — Identifier extraction probe.

A parametric `find_field_locations(sheet, shape, spec)` workhorse that, when
called once per FieldSpec, yields candidate cell locations + scope predictions
that map directly onto FieldLocator / PliEnumerationPlan / SheetLevelPlan.
"""
