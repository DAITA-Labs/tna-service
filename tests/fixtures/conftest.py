"""Pytest fixture loader for the FixtureCase system.

`fixture(request, tmp_path)` is indirectly parametrized via @fixture_case.
The parameter is a builder name. The loader:
  1. Imports tests.fixtures.builders.<name>.
  2. Builds a fresh Workbook in tmp_path.
  3. Loads tests/fixtures/expected/<name>.json.
  4. Registers via register_workbook for a fresh ctx.
  5. clear_cache() at setup AND teardown for isolation.

Builders may export `build(wb)` (xlsx workbook) OR `build_plan() -> SheetPlan`
(synthetic plan, used for plan-invariant failure cases). The loader detects
which is present.
"""
from __future__ import annotations
import importlib
import json
from pathlib import Path
import pytest
from openpyxl import Workbook
from app.repositories.workbook_repo import register_workbook, clear_cache
from tests.fixtures.case import FixtureCase

FIXTURES_ROOT = Path(__file__).resolve().parent
BUILDERS_DIR = FIXTURES_ROOT / "builders"
EXPECTED_DIR = FIXTURES_ROOT / "expected"


@pytest.fixture
def fixture(request, tmp_path) -> FixtureCase:
    name = request.param
    builder_path = BUILDERS_DIR / f"{name}.py"
    expected_path = EXPECTED_DIR / f"{name}.json"
    if not builder_path.exists():
        raise AssertionError(f"Fixture builder not found: {builder_path}")
    if not expected_path.exists():
        raise AssertionError(f"Fixture expected.json not found: {expected_path}")

    clear_cache()
    builder_mod = importlib.import_module(f"tests.fixtures.builders.{name}")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    if expected.get("fixture", name) != name:
        raise AssertionError(
            f"expected.json `fixture` field mismatch: {expected.get('fixture')} != {name}"
        )

    if hasattr(builder_mod, "build_plan"):
        ctx = None
        xlsx_path = None
    else:
        wb = Workbook()
        builder_mod.build(wb)
        xlsx_path = tmp_path / f"{name}.xlsx"
        wb.save(xlsx_path)
        ctx = register_workbook(xlsx_path)

    yield FixtureCase(name=name, ctx=ctx, xlsx_path=xlsx_path, _expected=expected)
    clear_cache()
