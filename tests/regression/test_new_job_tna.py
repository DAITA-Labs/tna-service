"""new job-TNA.xlsx is SHEET_IS_PLI — each of 5 sheets emits 1 PLI."""
from pathlib import Path
import pytest


@pytest.mark.live
def test_new_job_tna_five_plis_one_per_sheet():
    from app.services.extraction import extract
    p = Path("dataset/new job-TNA.xlsx")
    if not p.exists():
        pytest.skip("dataset file not present")
    result = extract(p)
    assert len(result.plis) == 5
    for pli in result.plis:
        assert pli.io_number is not None or pli.metadata.get("io_number") is not None
        assert len(pli.stages) >= 1
