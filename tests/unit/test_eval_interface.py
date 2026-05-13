"""Tests for evals/interface — Protocol acceptance."""
from pathlib import Path
from app.models.extraction import ExtractionResult, PLI
from evals.interface import ExtractorProtocol


class DummyExtractor:
    def extract(self, workbook_path: Path) -> ExtractionResult:
        return ExtractionResult(plis=[PLI(io_number="X")], source_file=str(workbook_path))


def test_extractor_protocol_accepts_compliant_class():
    """A class with `extract(Path) -> ExtractionResult` satisfies the Protocol."""
    e = DummyExtractor()
    assert isinstance(e, ExtractorProtocol)
    out = e.extract(Path("dummy.xlsx"))
    assert isinstance(out, ExtractionResult)
    assert out.plis[0].io_number == "X"
