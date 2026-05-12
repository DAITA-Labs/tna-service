"""Tests for app/core/logs."""
import json
from app.core.logs import configure_logging, get_logger


def test_get_logger_emits_structured_output(capsys):
    configure_logging(level="INFO", json_output=True)
    log = get_logger("test_module")
    log.info("agent_started", agent="inspector", file="x.xlsx")
    captured = capsys.readouterr().out.strip()
    # Should be parseable JSON with the named fields.
    parsed = json.loads(captured.splitlines()[-1])
    assert parsed["event"] == "agent_started"
    assert parsed["agent"] == "inspector"
    assert parsed["file"] == "x.xlsx"
    assert parsed["level"] == "info"


def test_configure_logging_respects_level(capsys):
    configure_logging(level="WARNING", json_output=False)
    log = get_logger("test_module")
    log.debug("should_not_appear")
    log.warning("should_appear")
    out = capsys.readouterr().out
    assert "should_appear" in out
    assert "should_not_appear" not in out
