"""
Preprocess node - deterministic text cleaning before LLM
"""

from datetime import datetime

from src.graph.state import BugTriageState
from src.utils.text_utils import preprocess_report
from src.utils.input_safety import classify_input, sanitize_report
from src.utils.logging import logger


def preprocess_node(state: BugTriageState) -> dict:
    """Strip noise, sanitize hostile input, extract stacktrace, compute hash."""
    start = datetime.now()
    text = state["bug_report_text"]

    logger.info(
        "node_start",
        node="preprocess",
        thread_id=state.get("thread_id"),
        report_length=len(text),
    )

    sanitized, safety_warnings = sanitize_report(text)
    cleaned, stacktrace, stacktrace_hash = preprocess_report(sanitized)
    input_quality = classify_input(cleaned)
    input_rejected = input_quality in ("off_topic", "too_short", "hostile")

    warnings: list[str] = list(safety_warnings)
    if input_rejected:
        warnings.append(f"Input flagged as {input_quality} — routed to human review")

    duration_ms = (datetime.now() - start).total_seconds() * 1000

    logger.info(
        "node_complete",
        node="preprocess",
        thread_id=state.get("thread_id"),
        has_stacktrace=stacktrace is not None,
        input_quality=input_quality,
        input_rejected=input_rejected,
        duration_ms=duration_ms,
    )

    result: dict = {
        "cleaned_report": cleaned,
        "extracted_stacktrace": stacktrace,
        "stacktrace_hash": stacktrace_hash,
        "input_rejected": input_rejected,
        "input_quality": input_quality,
        "node_timings": [{"node": "preprocess", "duration_ms": duration_ms}],
    }

    if warnings:
        result["processing_warnings"] = warnings
    if input_rejected:
        result["needs_human_review"] = True
        result["confidence"] = 0.0
        result["title"] = f"Review required: {input_quality.replace('_', ' ')} input"

    return result
