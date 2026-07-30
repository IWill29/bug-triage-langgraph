"""
LangGraph workflow definition
Builds the state graph with nodes and conditional routing
"""

from langgraph.graph import StateGraph, END
from typing import Literal

from src.graph.state import BugTriageState
# from src.graph.nodes import (
#     preprocess_node,
#     risk_check_node,
#     fast_triage_node,
#     premium_retry_node,
#     validate_node,
#     duplicate_check_node,
#     create_issue_node,
#     create_feature_node,
#     comment_duplicate_node,
# )


def route_risk_level(
    state: BugTriageState
) -> Literal["fast_triage", "create_issue"]:
    """
    Route based on risk assessment
    High-risk issues bypass ML triage
    """
    risk_level = state.get("risk_level", "safe")
    
    if risk_level == "escalate":
        # Security/data loss issues bypass ML
        return "create_issue"
    
    # Normal triage flow
    return "fast_triage"


def route_confidence(
    state: BugTriageState
) -> Literal["premium_retry", "validate", "duplicate_check"]:
    """
    Route based on extraction confidence
    Low confidence triggers premium model retry
    """
    # Max retries exhausted - skip to duplicate check
    if state.get("retry_count", 0) >= 3:
        return "duplicate_check"
    
    # Low confidence - try premium model
    if state.get("confidence", 0.0) < 0.70:
        return "premium_retry"
    
    # High confidence - validate output
    return "validate"


def route_validation(
    state: BugTriageState
) -> Literal["premium_retry", "duplicate_check"]:
    """
    Route based on validation result
    Failed validation triggers retry if retries remain
    """
    validation_errors = state.get("validation_errors", [])
    retry_count = state.get("retry_count", 0)
    
    # Validation passed or max retries
    if not validation_errors or retry_count >= 2:
        return "duplicate_check"
    
    # Validation failed - retry
    return "premium_retry"


def route_duplicate(
    state: BugTriageState
) -> Literal["comment_duplicate", "route_issue_type"]:
    """
    Route based on duplicate detection
    """
    if state.get("is_duplicate", False):
        return "comment_duplicate"
    
    return "route_issue_type"


def route_issue_type(
    state: BugTriageState
) -> Literal["create_bug", "create_feature"]:
    """
    Route based on issue type (bug vs feature request)
    """
    if state.get("is_feature_request", False):
        return "create_feature"
    
    return "create_bug"


def build_graph() -> StateGraph:
    """
    Build the LangGraph workflow
    
    Returns:
        StateGraph ready to compile with checkpointer
    """
    # Create state graph
    graph = StateGraph(BugTriageState)
    
    # TODO: Add nodes
    # graph.add_node("preprocess", preprocess_node)
    # graph.add_node("risk_check", risk_check_node)
    # graph.add_node("fast_triage", fast_triage_node)
    # graph.add_node("premium_retry", premium_retry_node)
    # graph.add_node("validate", validate_node)
    # graph.add_node("duplicate_check", duplicate_check_node)
    # graph.add_node("create_bug", create_issue_node)
    # graph.add_node("create_feature", create_feature_node)
    # graph.add_node("comment_duplicate", comment_duplicate_node)
    
    # TODO: Add edges
    # graph.set_entry_point("preprocess")
    # graph.add_edge("preprocess", "risk_check")
    # graph.add_conditional_edges("risk_check", route_risk_level)
    # graph.add_conditional_edges("fast_triage", route_confidence)
    # graph.add_conditional_edges("validate", route_validation)
    # graph.add_edge("premium_retry", "validate")
    # graph.add_conditional_edges("duplicate_check", route_duplicate)
    # graph.add_conditional_edges("route_issue_type", route_issue_type)
    # graph.add_edge("create_bug", END)
    # graph.add_edge("create_feature", END)
    # graph.add_edge("comment_duplicate", END)
    
    return graph
