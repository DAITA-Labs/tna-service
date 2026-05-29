"""Pickers — Haystack components that pick one winner from a candidate set.

Every picker shares the same shape: it owns a list of policies as data,
generates candidates from its inputs, runs every policy against every
candidate, aggregates verdicts, and emits the highest-scoring survivor
plus the full verdict trail.

See `app/components/pickers/_base.py` for the template; concrete pickers
live alongside in this package.
"""
from app.components.pickers._base import Picker

__all__ = ["Picker"]
