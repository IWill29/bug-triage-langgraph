"""
Validate node - schema and business rule validation with fallback defaults
"""

from datetime import datetime

from src.graph.state import BugTriageState
from src.utils.logging import logger


COSMETIC_KEYWORDS = ["typo", "copyright year", "footer", "color"]
SECURITY_KEYWORDS = ["sql injection", "xss", "vulnerable"]


def validate_node(state: BugTriageState) -> dict:
    """Validate extraction quality; apply safe defaults when retries exhausted."""
    start = datetime.now()
    errors: list[str] = []

    logger.info(
        "node_start",
        node="validate",
        thread_id=state.get("thread_id"),
        retry_count=state.get("retry_count", 0),
    )

    title = state.get("title")
    if not title or len(title) < 10:
        errors.append("title_too_short")
    if title and len(title) > 100:
        errors.append("title_too_long")

    components = state.get("components") or []
    if not components:
        errors.append("no_components_assigned")

    text = (state.get("cleaned_report") or "").lower()
    severity = state.get("severity")

    if severity == "critical" and any(kw in text for kw in COSMETIC_KEYWORDS):
        errors.append("severity_mismatch_cosmetic")

    if severity == "low" and any(kw in text for kw in SECURITY_KEYWORDS):
        errors.append("severity_mismatch_security")

    retry_count = state.get("retry_count", 0)
    duration_ms = (datetime.now() - start).total_seconds() * 1000

    if errors and retry_count >= 2:
        logger.warning(
            "validate_fallback_defaults",
            thread_id=state.get("thread_id"),
            errors=errors,
            retry_count=retry_count,
        )
        return {
            "severity": "medium",
            "components": components or ["unknown"],
            "needs_human_review": True,
            "validation_passed": True,
            "processing_warnings": [
                f"Applied fallback defaults after {retry_count} retries"
            ],
            "validation_errors": [{"errors": errors, "node": "validate"}],
            "node_timings": [{"node": "validate", "duration_ms": duration_ms}],
        }

    if errors:
        return {
            "validation_passed": False,
            "validation_errors": [{"errors": errors, "node": "validate"}],
            "node_timings": [{"node": "validate", "duration_ms": duration_ms}],
        }

    logger.info(
        "node_complete",
        node="validate",
        thread_id=state.get("thread_id"),
        valid=True,
        duration_ms=duration_ms,
    )

    return {
        "validation_passed": True,
        "node_timings": [{"node": "validate", "duration_ms": duration_ms}],
    }
