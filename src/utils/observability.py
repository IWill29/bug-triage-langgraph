"""
Observability setup — LangSmith tracing and structured log context.
"""

from __future__ import annotations

import os

from src.config import Settings
from src.utils.logging import logger


def configure_langsmith(settings: Settings) -> None:
    """Apply LangSmith environment variables when tracing is enabled."""
    if not settings.langsmith_tracing:
        os.environ.pop("LANGSMITH_TRACING", None)
        logger.info("langsmith_tracing_disabled")
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_TRACING_SAMPLING_RATE"] = str(
        settings.langsmith_sampling_rate
    )

    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        logger.info(
            "langsmith_configured",
            project=settings.langsmith_project,
            sampling_rate=settings.langsmith_sampling_rate,
        )
    else:
        logger.warning(
            "langsmith_tracing_requested_without_api_key",
            project=settings.langsmith_project,
        )
