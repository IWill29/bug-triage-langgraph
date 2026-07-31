"""
PostgresSaver checkpointer setup for production workflow persistence
"""

from contextlib import AbstractContextManager
from typing import Optional

from langgraph.checkpoint.postgres import PostgresSaver

from src.config import settings
from src.utils.logging import logger

_checkpointer_ctx: Optional[AbstractContextManager[PostgresSaver]] = None
_checkpointer: Optional[PostgresSaver] = None


def setup_checkpointer() -> PostgresSaver:
    """Create and initialize PostgresSaver with connection string from settings."""
    global _checkpointer_ctx, _checkpointer

    _checkpointer_ctx = PostgresSaver.from_conn_string(settings.database_url)
    _checkpointer = _checkpointer_ctx.__enter__()
    _checkpointer.setup()
    logger.info("checkpointer_ready", backend="postgres")
    return _checkpointer


def close_checkpointer() -> None:
    """Release PostgresSaver connection on shutdown."""
    global _checkpointer_ctx, _checkpointer

    if _checkpointer_ctx is not None:
        _checkpointer_ctx.__exit__(None, None, None)
        _checkpointer_ctx = None
        _checkpointer = None
        logger.info("checkpointer_closed")
