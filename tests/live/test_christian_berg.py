"""Live regression: CHRISTIAN BERG should produce 7 PLIs."""
import json
from pathlib import Path
import pytest


@pytest.mark.live
def test_christian_berg_seven_plis():
    from app.pipelines.extract import extract
    p = Path("dataset/CHRISTIAN BERG- T&A.xlsx")
    if not p.exists():
        pytest.skip("dataset file not present")
    result = extract(p)
    label_path = Path("dataset/extracted/CHRISTIAN BERG- T&A.json")
    label = json.loads(label_path.read_text())
    expected = label["total_plis"]
    assert len(result.plis) == expected, (
        f"expected {expected} PLIs, got {len(result.plis)}"
    )
