"""Cross-cutting framework concerns — logging, telemetry, middleware."""
from app.core.logs import configure_logging, get_logger
from app.core.middleware import RequestIdMiddleware
from app.core.pipeline_loader import load_pipeline_yaml
from app.core.prompt_loader import load_prompt
from app.core.telemetry import (
    agent_duration_seconds,
    agent_retry_count,
    agent_tokens_input,
    agent_tokens_output,
    extraction_duration_seconds,
    extraction_pli_count,
    llm_inference_duration_seconds,
    validator_findings_total,
)

__all__ = [
    "agent_duration_seconds",
    "agent_retry_count",
    "agent_tokens_input",
    "agent_tokens_output",
    "configure_logging",
    "extraction_duration_seconds",
    "extraction_pli_count",
    "get_logger",
    "llm_inference_duration_seconds",
    "load_pipeline_yaml",
    "load_prompt",
    "RequestIdMiddleware",
    "validator_findings_total",
]
