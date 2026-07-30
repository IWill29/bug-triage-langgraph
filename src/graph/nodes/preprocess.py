"""
Preprocess node - deterministic text cleaning before LLM
"""

from datetime import datetime

from src.graph.state import BugTriageState
from src.utils.text_utils import preprocess_report
from src.utils.logging import logger


def preprocess_node(state: BugTriageState) -> dict:
    """Strip noise, extract stacktrace, compute hash."""
    start = datetime.now()
    text = state["bug_report_text"]

    logger.info(
        "node_start",
        node="preprocess",
        thread_id=state.get("thread_id"),
        report_length=len(text),
    )

    cleaned, stacktrace, stacktrace_hash = preprocess_report(text)

    duration_ms = (datetime.now() - start).total_seconds() * 1000

    logger.info(
        "node_complete",
        node="preprocess",
        thread_id=state.get("thread_id"),
        has_stacktrace=stacktrace is not None,
        duration_ms=duration_ms,
    )

    return {
        "cleaned_report": cleaned,
        "extracted_stacktrace": stacktrace,
        "stacktrace_hash": stacktrace_hash,
        "node_timings": [{"node": "preprocess", "duration_ms": duration_ms}],
    }
