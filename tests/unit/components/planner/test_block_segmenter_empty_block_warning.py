"""block_segmenter logs an event when a PliBlock has no identity anchors."""
import logging
import structlog
from app.enums.row_role import RowRole
from app.models.artifacts import RowSpec
from app.components.planner.block_segmenter import segment_blocks


def test_empty_block_emits_log_event(caplog) -> None:
    rows = [
        RowSpec(idx=2, role=RowRole.ANCHOR),
        RowSpec(idx=5, role=RowRole.ANCHOR),
    ]
    # Reconfigure structlog to use stdlib LoggerFactory so caplog can capture logs.
    # This is needed because the app configures structlog with PrintLoggerFactory,
    # which bypasses Python's logging module that caplog hooks into.
    # We need to clear the cache to ensure the new factory is used.
    structlog.reset_defaults()
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),  # Render to string for stdlib logging
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,  # Don't cache to allow reconfiguration
    )
    # Force re-import of the module to get a fresh logger with new config
    import importlib
    import app.components.planner.block_segmenter
    importlib.reload(app.components.planner.block_segmenter)

    blocks = segment_blocks(rows=rows, kv_anchors=[], blank_run_gaps=[], stage_bands=[])
    assert len(blocks) == 2
    assert all(b.identity == [] for b in blocks)
    msgs = [r.message for r in caplog.records if "block_empty_identity" in r.message]
    # 2 blocks, 2 events.
    assert len(msgs) == 2
