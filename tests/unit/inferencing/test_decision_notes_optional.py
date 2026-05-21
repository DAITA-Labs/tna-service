"""decision_notes field is optional; render_prompt is gated by tuning."""
from __future__ import annotations

from app.artifacts.agent_io import AgentOutput, DECISION_NOTES_DIRECTIVE
from app.inferencing.tuning import AgentTuning, render_prompt


class CanonicalNameMapLike(AgentOutput):
    field_labels: dict[str, str] = {}


def test_agent_output_accepts_decision_notes_when_present() -> None:
    m = CanonicalNameMapLike(field_labels={"a": "b"}, decision_notes="because")
    assert m.decision_notes == "because"


def test_agent_output_decision_notes_defaults_to_none() -> None:
    m = CanonicalNameMapLike()
    assert m.decision_notes is None


def test_render_prompt_omits_directive_when_capture_disabled() -> None:
    tuning = AgentTuning(capture_decision_notes=False)
    out = render_prompt("BASE PROMPT", tuning=tuning)
    assert DECISION_NOTES_DIRECTIVE not in out


def test_render_prompt_appends_directive_when_capture_enabled() -> None:
    tuning = AgentTuning(capture_decision_notes=True)
    out = render_prompt("BASE PROMPT", tuning=tuning)
    assert DECISION_NOTES_DIRECTIVE in out
    assert out.startswith("BASE PROMPT")
