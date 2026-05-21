"""Running an extraction emits the three artifact snapshot logs."""
from __future__ import annotations

from structlog.testing import capture_logs

from app.services.extract_service import extract
from tests.fixtures.case import fixture_case
from tests.fixtures.fake_llm import FakeLLM


@fixture_case("tabular_simple")
def test_extract_emits_three_artifact_snapshots(fixture) -> None:
    """After planner, reviewer, and namer phases, three artifact snapshots are logged."""
    llm = FakeLLM(canned=fixture.fake_llm_responses())
    with capture_logs() as caps:
        result = extract(fixture.xlsx_path, llm=llm)
    assert len(result.plis) > 0, "Fixture should produce at least one PLI"
    log_events = [c["event"] for c in caps]
    assert "artifact.plan.snapshot_after_planner" in log_events
    assert "artifact.plan.snapshot_after_reviewer" in log_events
    assert "artifact.name_map.snapshot_after_namer" in log_events
