"""Tests for log_agent_io + log_artifact structured-log helpers."""
from __future__ import annotations

from structlog.testing import capture_logs

from app.core.log_capture import log_agent_io, log_artifact


def test_log_agent_io_emits_event_with_artifact_kind_and_agent() -> None:
    with capture_logs() as caps:
        log_agent_io("field_namer", kind="input", payload="full prompt text")
    assert caps, "no event captured"
    ev = caps[0]
    assert ev["event"] == "agent.input"
    assert ev["agent"] == "field_namer"
    assert ev["artifact_kind"] == "input"
    assert ev["payload"] == "full prompt text"


def test_log_agent_io_dict_payload_round_trips() -> None:
    with capture_logs() as caps:
        log_agent_io("plan_reviewer", kind="output",
                     payload={"verdict": "looks_correct"})
    assert caps[0]["payload"] == {"verdict": "looks_correct"}


def test_log_artifact_emits_named_event_under_artifact_prefix() -> None:
    with capture_logs() as caps:
        log_artifact("plan.snapshot_after_planner",
                     payload={"pli_mode": "ROW_PER_PLI"})
    assert caps[0]["event"] == "artifact.plan.snapshot_after_planner"
    assert caps[0]["artifact_kind"] == "snapshot"


def test_decision_notes_kind_uses_dedicated_event_name() -> None:
    with capture_logs() as caps:
        log_agent_io("field_namer", kind="decision_notes",
                     payload="one paragraph of reasoning")
    assert caps[0]["event"] == "agent.decision_notes"
