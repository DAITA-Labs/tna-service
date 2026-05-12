"""Cross-cutting framework concerns — logging, telemetry, middleware."""
from app.core.logs import configure_logging, get_logger
from app.core.telemetry import (
    extraction_duration_seconds, extraction_pli_count,
    agent_duration_seconds, agent_retry_count,
    agent_tokens_input, agent_tokens_output,
    validator_findings_total, llm_inference_duration_seconds,
)

__all__ = [
    "configure_logging", "get_logger",
    "extraction_duration_seconds", "extraction_pli_count",
    "agent_duration_seconds", "agent_retry_count",
    "agent_tokens_input", "agent_tokens_output",
    "validator_findings_total", "llm_inference_duration_seconds",
]
