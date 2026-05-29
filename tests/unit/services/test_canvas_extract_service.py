"""extract_canvas() — service-level orchestration tests with FakeLLM."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models.extraction import ExtractionResult
from app.services.canvas_extract_service import extract_canvas
from tests.fixtures.fake_llm import FakeLLM


def _mock_ctx(tmp_path: Path) -> SimpleNamespace:
    """Build a fake WorkbookCtx exposing the attributes the service touches."""
    return SimpleNamespace(path=tmp_path / "fake.xlsx", wb=MagicMock())


# ─── Empty-workbook path ─────────────────────────────────────────────────


def test_empty_bundles_returns_warning(tmp_path: Path) -> None:
    """When WorkbookPhase finds no PLI clusters, the service returns an
    empty result with a single 'no PLI clusters' warning. The LLM is
    never invoked.
    """
    ctx = _mock_ctx(tmp_path)
    with patch("app.services.canvas_extract_service.register_workbook", return_value=ctx), \
         patch("app.services.canvas_extract_service.WorkbookPhase") as MockPhase:
        MockPhase.return_value.run.return_value = {"bundles": []}
        result = extract_canvas(ctx.path, llm=FakeLLM(canned={}))

    assert isinstance(result, ExtractionResult)
    assert result.plis == []
    assert len(result.warnings) == 1
    assert "No PLI clusters" in result.warnings[0].message


def test_empty_bundles_skips_llm(tmp_path: Path) -> None:
    """FakeLLM with no canned response would crash if called; this confirms
    the early-return path is taken when there are zero bundles.
    """
    ctx = _mock_ctx(tmp_path)
    with patch("app.services.canvas_extract_service.register_workbook", return_value=ctx), \
         patch("app.services.canvas_extract_service.WorkbookPhase") as MockPhase:
        MockPhase.return_value.run.return_value = {"bundles": []}
        # No canned responses → any LLM call would raise.
        result = extract_canvas(ctx.path, llm=FakeLLM(canned={}))

    assert result.plis == []


def test_source_file_attached_to_result(tmp_path: Path) -> None:
    ctx = _mock_ctx(tmp_path)
    with patch("app.services.canvas_extract_service.register_workbook", return_value=ctx), \
         patch("app.services.canvas_extract_service.WorkbookPhase") as MockPhase:
        MockPhase.return_value.run.return_value = {"bundles": []}
        result = extract_canvas(ctx.path, llm=FakeLLM(canned={}))

    assert result.source_file == str(ctx.path)
