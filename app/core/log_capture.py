"""Structured-log helpers for agent I/O and inter-phase artifact snapshots.

Trace context (`trace_id` + `span_id`) is added automatically by the
structlog processor chain configured in `app.core.tracing`, so callers
do not pass them. Emit events with this module's helpers wherever full
text capture matters; the events show up in SigNoz Logs Explorer joined
to the request's trace.
"""
from __future__ import annotations

from typing import Any, Literal

from app.core.logs import get_logger

IoKind = Literal["input", "response", "output", "decision_notes"]

_log = get_logger("app.agent_io")


def log_agent_io(agent: str, *, kind: IoKind, payload: Any) -> None:
    """Emit a structured log carrying the full agent prompt / response / output."""
    _log.info(
        f"agent.{kind}",
        agent=agent,
        artifact_kind=kind,
        payload=payload,
    )


def log_artifact(name: str, *, payload: Any) -> None:
    """Emit a structured log carrying an inter-phase artifact snapshot."""
    _log.info(
        f"artifact.{name}",
        artifact_kind="snapshot",
        payload=payload,
    )
