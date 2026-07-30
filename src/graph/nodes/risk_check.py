"""
Risk check node - safety override for high-risk reports
"""

from datetime import datetime

from src.graph.state import BugTriageState
from src.utils.text_utils import detect_pii
from src.utils.logging import logger


SECURITY_KEYWORDS = [
    "sql injection",
    "xss",
    "csrf",
    "rce",
    "command injection",
]

DATA_LOSS_KEYWORDS = [
    "deleted all",
    "lost data",
    "corrupted database",
]


def risk_check_node(state: BugTriageState) -> dict:
    """Check for patterns requiring immediate escalation."""
    start = datetime.now()
    text = state["cleaned_report"].lower()
    signals: list[str] = []

    logger.info(
        "node_start",
        node="risk_check",
        thread_id=state.get("thread_id"),
    )

    if any(kw in text for kw in SECURITY_KEYWORDS):
        signals.append("security_vulnerability")
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        return {
            "risk_level": "escalate",
            "risk_signals": signals,
            "severity": "critical",
            "confidence": 1.0,
            "needs_human_review": True,
            "node_timings": [{"node": "risk_check", "duration_ms": duration_ms}],
        }

    if any(kw in text for kw in DATA_LOSS_KEYWORDS):
        signals.append("data_loss_potential")
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        return {
            "risk_level": "escalate",
            "risk_signals": signals,
            "severity": "critical",
            "confidence": 1.0,
            "needs_human_review": True,
            "node_timings": [{"node": "risk_check", "duration_ms": duration_ms}],
        }

    if detect_pii(text):
        signals.append("pii_exposure")
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        return {
            "risk_level": "review",
            "risk_signals": signals,
            "needs_human_review": True,
            "node_timings": [{"node": "risk_check", "duration_ms": duration_ms}],
        }

    duration_ms = (datetime.now() - start).total_seconds() * 1000
    logger.info(
        "node_complete",
        node="risk_check",
        thread_id=state.get("thread_id"),
        risk_level="safe",
        duration_ms=duration_ms,
    )

    return {
        "risk_level": "safe",
        "risk_signals": [],
        "node_timings": [{"node": "risk_check", "duration_ms": duration_ms}],
    }
