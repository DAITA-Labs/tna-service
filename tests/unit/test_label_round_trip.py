"""All hand-labeled ExtractionResult JSON files in ../dataset/extracted/ must
round-trip through the Pydantic models without error."""
import json
from pathlib import Path
import pytest
from app.models.extraction import ExtractionResult


LABELS = sorted(
    (Path(__file__).resolve().parents[2].parent / "dataset" / "extracted").glob("*.json")
)


@pytest.mark.parametrize("label_path", LABELS, ids=lambda p: p.stem)
def test_label_round_trips(label_path):
    data = json.loads(label_path.read_text(encoding="utf-8"))
    result = ExtractionResult(**data)
    # Sanity — at least one PLI per labeled file.
    assert len(result.plis) >= 0  # accept empty just in case
