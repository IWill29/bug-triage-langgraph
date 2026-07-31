"""
Gitea integration nodes - issue creation, duplicate comments, human review
"""

from datetime import datetime
from typing import Literal

from src.graph.state import BugTriageState
from src.services.gitea_service import gitea_service
from src.config import settings
from src.utils.logging import logger


def _format_warnings(warnings: list[str]) -> str:
    if not warnings:
        return ""
    lines = "\n".join(f"- {warning}" for warning in warnings)
    return f"\n### Warnings\n{lines}\n"


def human_review_node(state: BugTriageState) -> dict:
    """Queue report for human review (PII, security escalation)."""
    start = datetime.now()
    cleaned = state.get("cleaned_report") or state.get("bug_report_text", "")
    title = state.get("title") or f"Review required: {cleaned[:50]}..."

    logger.info(
        "node_start",
        node="human_review",
        thread_id=state.get("thread_id"),
        risk_level=state.get("risk_level"),
    )

    duration_ms = (datetime.now() - start).total_seconds() * 1000

    if state.get("input_rejected"):
        reason = state.get("input_quality") or "invalid"
        warning = f"Input rejected ({reason}) — requires human review"
    else:
        warning = f"Report flagged for human review (risk_level={state.get('risk_level')})"

    default_severity = "medium" if state.get("input_rejected") else "high"

    return {
        "title": title,
        "severity": state.get("severity") or default_severity,
        "needs_human_review": True,
        "processing_warnings": [warning],
        "node_timings": [{"node": "human_review", "duration_ms": duration_ms}],
    }


def route_issue_creation(
    state: BugTriageState,
) -> Literal["create_bug", "create_feature"]:
    """Route to appropriate issue creation based on type."""
    if state.get("is_feature_request", False):
        return "create_feature"
    return "create_bug"


def create_issue_node(state: BugTriageState) -> dict:
    """Create new Gitea bug issue."""
    start = datetime.now()

    logger.info(
        "node_start",
        node="create_issue",
        thread_id=state.get("thread_id"),
        title=state.get("title"),
    )

    warnings = state.get("processing_warnings") or []
    model_label = "Premium (GPT-4o)" if state.get("used_premium_model") else "Fast (GPT-4o-mini)"
    candidates = state.get("duplicate_candidates") or []

    body = f"""## Bug Report

{state["cleaned_report"]}

---

### Reproduction Steps
{state.get("reproduction_steps") or "_Not provided_"}

---

### Triage Details
- **Severity:** {state.get("severity", "medium")}
- **Confidence:** {state.get("confidence", 0.0):.2f}
- **Model:** {model_label}
- **Duplicate Check:** {len(candidates)} similar issues reviewed
{_format_warnings(warnings)}"""

    if state.get("stacktrace_hash"):
        body += f"\n<!-- stacktrace_hash:{state['stacktrace_hash']} -->\n"

    labels = list(state.get("components") or ["unknown"])

    try:
        issue = gitea_service.create_issue_sync(
            title=state["title"],
            body=body,
            labels=labels,
        )
        issue_url = issue.get("html_url") or (
            f"{settings.gitea_url}/issues/{issue.get('number')}"
        )
    except Exception as exc:
        logger.error(
            "create_issue_failed",
            thread_id=state.get("thread_id"),
            error=str(exc),
        )
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        return {
            "needs_human_review": True,
            "processing_warnings": [f"Gitea issue creation failed: {type(exc).__name__}"],
            "node_timings": [{"node": "create_issue", "duration_ms": duration_ms}],
        }

    duration_ms = (datetime.now() - start).total_seconds() * 1000

    logger.info(
        "node_complete",
        node="create_issue",
        thread_id=state.get("thread_id"),
        issue_url=issue_url,
        duration_ms=duration_ms,
    )

    return {
        "gitea_issue_url": issue_url,
        "node_timings": [{"node": "create_issue", "duration_ms": duration_ms}],
    }


def create_feature_node(state: BugTriageState) -> dict:
    """Create new Gitea feature request issue."""
    start = datetime.now()

    logger.info(
        "node_start",
        node="create_feature",
        thread_id=state.get("thread_id"),
        title=state.get("title"),
    )

    warnings = state.get("processing_warnings") or []
    components = state.get("components") or ["unknown"]

    body = f"""## Feature Request

{state["cleaned_report"]}

---

### Proposed Functionality
{state.get("reproduction_steps") or "_Details not provided_"}

---

### Triage Details
- **Type:** Enhancement / Feature Request
- **Confidence:** {state.get("confidence", 0.0):.2f}
- **Suggested Components:** {', '.join(components)}
{_format_warnings(warnings)}"""

    labels = ["enhancement", "feature-request"] + list(components)

    try:
        issue = gitea_service.create_issue_sync(
            title=state["title"],
            body=body,
            labels=labels,
        )
        issue_url = issue.get("html_url") or (
            f"{settings.gitea_url}/issues/{issue.get('number')}"
        )
    except Exception as exc:
        logger.error(
            "create_feature_failed",
            thread_id=state.get("thread_id"),
            error=str(exc),
        )
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        return {
            "needs_human_review": True,
            "processing_warnings": [f"Gitea feature creation failed: {type(exc).__name__}"],
            "node_timings": [{"node": "create_feature", "duration_ms": duration_ms}],
        }

    duration_ms = (datetime.now() - start).total_seconds() * 1000

    return {
        "gitea_issue_url": issue_url,
        "node_timings": [{"node": "create_feature", "duration_ms": duration_ms}],
    }


def comment_duplicate_node(state: BugTriageState) -> dict:
    """Add comment to existing duplicate issue."""
    start = datetime.now()
    cleaned = state.get("cleaned_report") or ""
    snippet = cleaned[:500]

    logger.info(
        "node_start",
        node="comment_duplicate",
        thread_id=state.get("thread_id"),
        duplicate_issue_id=state.get("duplicate_issue_id"),
    )

    comment = f"""## Duplicate Report Received

A similar bug report was submitted:

{snippet}{"..." if len(cleaned) > 500 else ""}

**Duplicate Confidence:** {state.get("duplicate_confidence", 0.0):.2f}

_This issue has been automatically linked as a duplicate._
"""

    issue_id = state["duplicate_issue_id"]

    try:
        gitea_service.add_comment_sync(issue_id=issue_id, body=comment)
        issue_url = f"{settings.gitea_url}/issues/{issue_id}"
    except Exception as exc:
        logger.error(
            "comment_duplicate_failed",
            thread_id=state.get("thread_id"),
            error=str(exc),
        )
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        return {
            "needs_human_review": True,
            "processing_warnings": [f"Duplicate comment failed: {type(exc).__name__}"],
            "node_timings": [{"node": "comment_duplicate", "duration_ms": duration_ms}],
        }

    duration_ms = (datetime.now() - start).total_seconds() * 1000

    return {
        "gitea_issue_url": issue_url,
        "node_timings": [{"node": "comment_duplicate", "duration_ms": duration_ms}],
    }
