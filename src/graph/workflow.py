"""
LangGraph workflow definition
Builds the state graph with nodes and conditional routing
"""

from langgraph.graph import StateGraph, END
from langgraph.types import RetryPolicy
from pydantic import ValidationError
from typing import Literal

from src.graph.state import BugTriageState
from src.graph.nodes.preprocess import preprocess_node
from src.graph.nodes.risk_check import risk_check_node
from src.graph.nodes.triage import (
    fast_triage_node,
    premium_retry_node,
    route_confidence,
)
from src.graph.nodes.validate import validate_node
from src.graph.nodes.duplicate import duplicate_check_node
from src.graph.nodes.gitea import (
    create_issue_node,
    create_feature_node,
    comment_duplicate_node,
    human_review_node,
    route_issue_creation,
)
from src.utils.logging import logger


def route_risk_level(
    state: BugTriageState,
) -> Literal["fast_triage", "human_review"]:
    """Route based on risk assessment."""
    risk_level = state.get("risk_level", "safe")
    if risk_level in ("escalate", "review"):
        return "human_review"
    return "fast_triage"


def route_validation(
    state: BugTriageState,
) -> Literal["premium_retry", "duplicate_check"]:
    """Route based on validation result."""
    retry_count = state.get("retry_count", 0)

    if state.get("validation_passed", False):
        return "duplicate_check"

    if retry_count >= 2:
        return "duplicate_check"

    return "premium_retry"


def route_duplicate(
    state: BugTriageState,
) -> Literal["comment_duplicate", "create_bug", "create_feature"]:
    """Route based on duplicate detection and issue type."""
    if state.get("is_duplicate", False):
        return "comment_duplicate"
    return route_issue_creation(state)


def handle_triage_error(error: Exception, state: BugTriageState) -> dict:
    """Graceful degradation on triage failure."""
    logger.error(
        "triage_node_failed",
        error=str(error),
        error_type=type(error).__name__,
        retry_count=state.get("retry_count", 0),
        thread_id=state.get("thread_id"),
    )
    return {
        "severity": "medium",
        "components": ["unknown"],
        "confidence": 0.0,
        "needs_human_review": True,
        "processing_warnings": [f"Triage failed: {type(error).__name__}"],
    }


def handle_duplicate_error(error: Exception, state: BugTriageState) -> dict:
    """Graceful degradation on duplicate check failure."""
    logger.error(
        "duplicate_check_failed",
        error=str(error),
        error_type=type(error).__name__,
        thread_id=state.get("thread_id"),
    )
    return {
        "is_duplicate": False,
        "duplicate_candidates": [],
        "processing_warnings": [f"Duplicate check failed: {type(error).__name__}"],
    }


def build_graph() -> StateGraph:
    """
    Build the LangGraph workflow.

    Returns:
        StateGraph ready to compile with checkpointer
    """
    graph = StateGraph(BugTriageState)

    graph.add_node("preprocess", preprocess_node)
    graph.add_node("risk_check", risk_check_node)
    graph.add_node(
        "fast_triage",
        fast_triage_node,
        retry_policy=RetryPolicy(
            retry_on=ValidationError,
            max_attempts=3,
            initial_interval=0.5,
            backoff_factor=2.0,
        ),
        error_handler=handle_triage_error,
    )
    graph.add_node(
        "premium_retry",
        premium_retry_node,
        retry_policy=RetryPolicy(
            retry_on=ValidationError,
            max_attempts=3,
            initial_interval=0.5,
            backoff_factor=2.0,
        ),
        error_handler=handle_triage_error,
    )
    graph.add_node("validate", validate_node)
    graph.add_node(
        "duplicate_check",
        duplicate_check_node,
        error_handler=handle_duplicate_error,
    )
    graph.add_node("create_bug", create_issue_node)
    graph.add_node("create_feature", create_feature_node)
    graph.add_node("comment_duplicate", comment_duplicate_node)
    graph.add_node("human_review", human_review_node)

    graph.set_entry_point("preprocess")
    graph.add_edge("preprocess", "risk_check")

    graph.add_conditional_edges(
        "risk_check",
        route_risk_level,
        {
            "fast_triage": "fast_triage",
            "human_review": "human_review",
        },
    )

    graph.add_conditional_edges(
        "fast_triage",
        route_confidence,
        {
            "premium_retry": "premium_retry",
            "validate": "validate",
            "duplicate_check": "duplicate_check",
        },
    )

    graph.add_edge("premium_retry", "validate")

    graph.add_conditional_edges(
        "validate",
        route_validation,
        {
            "premium_retry": "premium_retry",
            "duplicate_check": "duplicate_check",
        },
    )

    graph.add_conditional_edges(
        "duplicate_check",
        route_duplicate,
        {
            "comment_duplicate": "comment_duplicate",
            "create_bug": "create_bug",
            "create_feature": "create_feature",
        },
    )

    graph.add_edge("create_bug", END)
    graph.add_edge("create_feature", END)
    graph.add_edge("comment_duplicate", END)
    graph.add_edge("human_review", END)

    return graph
