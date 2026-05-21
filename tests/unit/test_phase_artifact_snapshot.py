"""log_artifact emits one artifact log per named phase."""
from __future__ import annotations

from structlog.testing import capture_logs

from app.core.log_capture import log_artifact


def test_snapshot_emits_artifact_log_for_named_phase() -> None:
    with capture_logs() as caps:
        log_artifact("plan.snapshot_after_planner",
                     payload={"pli_mode": "ROW_PER_PLI"})
    assert caps[0]["event"] == "artifact.plan.snapshot_after_planner"
    assert caps[0]["payload"] == {"pli_mode": "ROW_PER_PLI"}
    assert caps[0]["artifact_kind"] == "snapshot"
