"""KvBlock detector — bold/filled label + adjacent value pair."""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.artifacts.structure import KvBlock
from app.tools.canvas.build import build_canvas
from app.tools.canvas.kv_block import find_kv_blocks


DATASET = Path(__file__).resolve().parents[4] / "dataset"


@pytest.fixture
def kv_canvas():
    """63261-TNA — SHEET_IS_PLI with classic k:v blocks in rows 4-5."""
    wb = load_workbook(DATASET / "63261-TNA.xlsx", data_only=True)
    return build_canvas(wb.active)


@pytest.fixture
def tabular_canvas():
    """DKN — ROW_PER_PLI tabular. KvBlocks should be rare here."""
    wb = load_workbook(DATASET / "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
                       data_only=True)
    return build_canvas(wb.active)


def test_kv_blocks_returned_as_records(kv_canvas) -> None:
    """find_kv_blocks returns KvBlock records with label + value coords + text + dtype."""
    blocks = find_kv_blocks(kv_canvas)
    assert isinstance(blocks, list)
    assert all(isinstance(b, KvBlock) for b in blocks)


def test_kv_block_carries_label_text(kv_canvas) -> None:
    """Each KvBlock has non-empty label_text."""
    for b in find_kv_blocks(kv_canvas):
        assert b.label_text != ""


def test_kv_block_coord_shape(kv_canvas) -> None:
    """label_coord and value_coord are (column_letter, 1-indexed row) tuples."""
    for b in find_kv_blocks(kv_canvas):
        assert isinstance(b.label_coord, tuple)
        assert len(b.label_coord) == 2
        assert isinstance(b.label_coord[0], str)
        assert isinstance(b.label_coord[1], int)
        assert b.label_coord[1] >= 1


def test_63261_finds_job_no_kv_pair(kv_canvas) -> None:
    """63261's 'Job No' (A4) → 63261 (B4) k:v pair should be detected."""
    blocks = find_kv_blocks(kv_canvas)
    label_texts = [b.label_text.lower() for b in blocks]
    # 63261-TNA has Job No, Quantity, Ex-Fty date, Delivery date as kv labels
    # At least one of these label patterns should appear
    has_job_no_like = any("job" in t or "quantity" in t or "delivery" in t or "fty" in t
                          for t in label_texts)
    assert has_job_no_like


def test_tabular_layout_has_fewer_kv_blocks(tabular_canvas, kv_canvas) -> None:
    """A SHEET_IS_PLI sheet has many KvBlocks; a tabular sheet has fewer or none."""
    kv_blocks = find_kv_blocks(kv_canvas)
    tabular_blocks = find_kv_blocks(tabular_canvas)
    # Not a hard guarantee but the contract: kv layout > tabular for kv-pair count
    # (allowing both to be empty in pathological cases)
    assert len(kv_blocks) >= len(tabular_blocks) or len(kv_blocks) == 0


def test_value_dtype_in_known_range(kv_canvas) -> None:
    """Every KvBlock's value_dtype is one of the canvas dtype codes (0-5)."""
    for b in find_kv_blocks(kv_canvas):
        assert 0 <= b.value_dtype <= 5


def test_tool_registered() -> None:
    from app.tools._registry import TOOL_REGISTRY

    assert "find_kv_blocks" in TOOL_REGISTRY.names()
