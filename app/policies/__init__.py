"""Policies — pluggable scoring/elimination functions consumed by Pickers.

A policy is a callable that takes a candidate (row, column, KvBlock,
canonical name, etc.) plus arbitrary context kwargs and returns one
`PolicyVerdict` describing whether the candidate is boosted, penalised,
or eliminated.

Pickers (`app/components/pickers/`) own a list of policies and run them
against every candidate, then aggregate the verdicts to pick a winner.
"""
from app.policies._base import PolicyVerdict, aggregate_verdicts

__all__ = ["PolicyVerdict", "aggregate_verdicts"]
