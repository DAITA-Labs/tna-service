"""FixtureCase: a single test scenario, materialized.

The `fixture` pytest fixture (in conftest.py) builds FixtureCase instances
from a fixture name. Tests consume FixtureCase to read ctx / sheets /
expected assertions.

`fixture_case(*names)` is sugar over @pytest.mark.parametrize so tests can
declare which scenarios they run against without re-typing the parametrize
incantation.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import pytest


@dataclass(frozen=True)
class FixtureCase:
    name: str
    ctx: Any
    xlsx_path: Path | None
    _expected: dict

    @property
    def sheets(self) -> list[str]:
        return list(self.ctx.wb.sheetnames) if self.ctx is not None else []

    @property
    def sheet(self) -> str:
        if not self.sheets:
            raise AssertionError(f"Fixture {self.name!r} has no sheets")
        return self.sheets[0]

    @property
    def description(self) -> str:
        return self._expected.get("description", "")

    def expectations(self, tier: str) -> dict:
        per_tier = (self._expected.get("layer_expectations") or {}).get(tier)
        if per_tier is None:
            raise AssertionError(
                f"Fixture {self.name!r} has no `layer_expectations.{tier}` "
                f"declared in expected.json"
            )
        return per_tier

    def failure_expectations(self) -> dict | None:
        return self._expected.get("failure_expectations")

    def is_failure_case(self) -> bool:
        return self.failure_expectations() is not None

    def fake_llm_responses(self) -> dict:
        return self.expectations("e2e").get("fake_llm_responses", {})


def fixture_case(*names: str):
    """Parametrize the test over named fixtures.

    Usage:
        @fixture_case("tabular_simple")
        def test_one(fixture):
            ...

        @fixture_case("tabular_simple", "tabular_with_totals")
        def test_many(fixture):
            ...
    """
    if not names:
        raise ValueError("@fixture_case requires at least one fixture name")
    return pytest.mark.parametrize("fixture", names, indirect=True, ids=list(names))
