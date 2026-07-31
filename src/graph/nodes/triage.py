"""
Triage nodes - fast and premium LLM extraction with confidence routing
"""

from datetime import datetime
from typing import Literal

from pydantic import ValidationError
from langchain_core.prompts import ChatPromptTemplate

from src.graph.state import BugTriageState
from src.models.triage import TriageExtraction
from src.services.llm_service import llm_service
from src.config import settings
from src.utils.logging import logger


FAST_TRIAGE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a bug triage assistant. Extract structured information.

Rules:
- Title: concise, actionable (e.g. "Login button unresponsive on mobile Safari")
- Severity:
  * critical = data loss, security, complete system down
  * high = major feature broken, affects many users
  * medium = feature degraded, workaround exists
  * low = cosmetic, typos, minor UX
- Components: choose 1-3 most relevant
- Reproduction steps: extract if present, else null (DO NOT invent)
- Confidence: 0.0-1.0 based on report clarity
- Flag feature requests (not bugs)
- Multiple issues: if report describes 2+ distinct problems, set multiple_issues_detected=true
  and list secondary issues briefly (primary goes in title)""",
    ),
    ("user", "{bug_report}"),
])


def _build_premium_prompt(state: BugTriageState) -> str:
    """Build premium retry prompt with error feedback."""
    previous_errors = state.get("validation_errors", [])
    error_feedback = ""
    if previous_errors:
        last_error = previous_errors[-1]
        error_text = last_error.get("error") or last_error.get("errors", last_error)
        error_feedback = f"\nPrevious extraction failed: {error_text}"

    return f"""Bug report classification (RETRY with corrections):

Report: {state["cleaned_report"]}

Previous attempt (confidence {state.get("confidence", 0.0)}):
- Title: {state.get("title", "N/A")}
- Severity: {state.get("severity", "N/A")}
{error_feedback}

Re-extract with higher accuracy. Focus on:
1. More precise severity assessment
2. Complete component coverage
3. Clear reproduction steps (or explicit null)"""


def _extraction_to_state(
    result: TriageExtraction,
    model: str,
    *,
    sticky_human_review: bool = False,
) -> dict:
    """Map TriageExtraction to state delta."""
    warnings: list[str] = []
    if result.multiple_issues_detected and result.secondary_issues:
        warnings.append(
            f"Multiple issues detected. Secondary: {', '.join(result.secondary_issues)}"
        )

    flag_human_review = (
        result.confidence <= settings.confidence_threshold or sticky_human_review
    )

    if result.confidence <= settings.confidence_threshold:
        warnings.append(
            f"Low confidence ({result.confidence:.2f}) - flagged for human review"
        )
    elif sticky_human_review:
        warnings.append(
            f"Human review preserved after retry (confidence {result.confidence:.2f})"
        )

    delta: dict = {
        "title": result.title,
        "severity": result.severity,
        "components": list(result.components),
        "reproduction_steps": result.reproduction_steps,
        "confidence": result.confidence,
        "is_feature_request": result.is_feature_request,
        "multiple_issues_detected": result.multiple_issues_detected,
        "secondary_issues": result.secondary_issues,
        "processing_warnings": warnings,
        "classification_history": [{
            "model": model,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "timestamp": datetime.now().isoformat(),
        }],
    }

    if flag_human_review:
        delta["needs_human_review"] = True

    return delta


def fast_triage_node(state: BugTriageState) -> dict:
    """Extract structured triage info with fast model."""
    start = datetime.now()

    logger.info(
        "node_start",
        node="fast_triage",
        thread_id=state.get("thread_id"),
        retry_count=state.get("retry_count", 0),
    )

    try:
        prompt = FAST_TRIAGE_PROMPT.format(bug_report=state["cleaned_report"])
        result = llm_service.invoke_fast(prompt, TriageExtraction)
        delta = _extraction_to_state(result, settings.fast_model)
    except ValidationError as exc:
        logger.warning(
            "fast_triage_validation_failed",
            thread_id=state.get("thread_id"),
            error=str(exc),
        )
        return {
            "confidence": 0.0,
            "validation_errors": [{
                "error": str(exc),
                "node": "fast_triage",
                "timestamp": datetime.now().isoformat(),
            }],
        }
    except Exception as exc:
        logger.error(
            "fast_triage_failed",
            thread_id=state.get("thread_id"),
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return {
            "confidence": 0.0,
            "severity": "medium",
            "components": ["unknown"],
            "needs_human_review": True,
            "processing_warnings": [f"Triage failed: {type(exc).__name__}"],
            "validation_errors": [{
                "error": str(exc),
                "node": "fast_triage",
                "timestamp": datetime.now().isoformat(),
            }],
        }

    duration_ms = (datetime.now() - start).total_seconds() * 1000
    delta["node_timings"] = [{"node": "fast_triage", "duration_ms": duration_ms}]

    logger.info(
        "node_complete",
        node="fast_triage",
        thread_id=state.get("thread_id"),
        confidence=delta.get("confidence"),
        duration_ms=duration_ms,
    )

    return delta


def premium_retry_node(state: BugTriageState) -> dict:
    """Retry with premium model and error feedback."""
    start = datetime.now()

    logger.info(
        "node_start",
        node="premium_retry",
        thread_id=state.get("thread_id"),
        retry_count=state.get("retry_count", 0),
    )

    try:
        prompt = _build_premium_prompt(state)
        result = llm_service.invoke_premium(prompt, TriageExtraction)
        sticky_human_review = (
            state.get("needs_human_review", False)
            or state.get("confidence", 0.0) <= settings.confidence_threshold
        )
        delta = _extraction_to_state(
            result,
            settings.premium_model,
            sticky_human_review=sticky_human_review,
        )
        delta["retry_count"] = state.get("retry_count", 0) + 1
        delta["used_premium_model"] = True
    except ValidationError as exc:
        logger.warning(
            "premium_retry_validation_failed",
            thread_id=state.get("thread_id"),
            error=str(exc),
        )
        return {
            "confidence": 0.0,
            "retry_count": state.get("retry_count", 0) + 1,
            "used_premium_model": True,
            "validation_errors": [{
                "error": str(exc),
                "node": "premium_retry",
                "timestamp": datetime.now().isoformat(),
            }],
        }
    except Exception as exc:
        logger.error(
            "premium_retry_failed",
            thread_id=state.get("thread_id"),
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return {
            "confidence": 0.0,
            "retry_count": state.get("retry_count", 0) + 1,
            "used_premium_model": True,
            "severity": "medium",
            "components": ["unknown"],
            "needs_human_review": True,
            "processing_warnings": [f"Premium retry failed: {type(exc).__name__}"],
            "validation_errors": [{
                "error": str(exc),
                "node": "premium_retry",
                "timestamp": datetime.now().isoformat(),
            }],
        }

    duration_ms = (datetime.now() - start).total_seconds() * 1000
    delta["node_timings"] = [{"node": "premium_retry", "duration_ms": duration_ms}]

    logger.info(
        "node_complete",
        node="premium_retry",
        thread_id=state.get("thread_id"),
        confidence=delta.get("confidence"),
        retry_count=delta.get("retry_count"),
        duration_ms=duration_ms,
    )

    return delta


def route_confidence(
    state: BugTriageState,
) -> Literal["premium_retry", "validate", "duplicate_check"]:
    """Route based on extraction confidence with bounded retries."""
    if state.get("retry_count", 0) >= settings.max_retries:
        return "duplicate_check"

    if state.get("confidence", 0.0) <= settings.confidence_threshold:
        return "premium_retry"

    return "validate"
