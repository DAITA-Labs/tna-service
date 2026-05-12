"""Tests for app/services/extraction (the orchestrator)."""
from unittest.mock import patch, MagicMock
from app.services.extraction import extract


def test_orchestrator_halts_on_empty_relevant_sheets(dkn_file):
    """If SheetClassifier yields no relevant_sheets, result is empty + warning."""
    with patch("app.services.extraction.AnthropicProvider") as mock_prov, \
         patch("app.services.extraction.SheetClassifier") as MockCls:
        instance = MagicMock()
        instance.run.return_value = {"relevant_sheets": []}
        MockCls.return_value = instance
        mock_prov.from_env.return_value = MagicMock()
        result = extract(dkn_file)
    assert result.plis == []
    assert any("no relevant sheets" in w.message.lower() for w in result.warnings)
