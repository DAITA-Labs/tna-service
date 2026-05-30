"""Stages-layer policies — score detected stage bands.

Unlike field pickers (single winner per canonical), the stages flow is
multi-winner: every band scoring above a floor survives. Policies in
this layer score individual bands (presence / overlap signals) and
cross-band rules (anchor row alignment, no overlapping column ranges)
that mutate or eliminate bands.
"""
