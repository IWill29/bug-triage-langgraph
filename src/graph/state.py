"""
State schema for LangGraph workflow
Defines immutable state with accumulator fields
"""

from typing import Annotated, TypedDict, Literal, Optional
import operator


class BugTriageState(TypedDict):
    """
    Immutable state with accumulator fields
    Nodes return only changed keys, reducers merge updates
    """
    
    # ========== INPUT ==========
    bug_report_text: str                    # Raw input from user
    thread_id: str                          # Unique execution ID
    
    # ========== PREPROCESSING ==========
    cleaned_report: Optional[str]           # Noise-stripped text
    extracted_stacktrace: Optional[str]     # Isolated stack trace
    stacktrace_hash: Optional[str]          # Hash for fast dedup
    
    # ========== RISK ASSESSMENT ==========
    risk_level: Optional[Literal["safe", "review", "escalate"]]
    risk_signals: Annotated[list[str], operator.add]  # Accumulates
    
    # ========== LLM EXTRACTION ==========
    title: Optional[str]                    # Generated title
    severity: Optional[Literal["critical", "high", "medium", "low"]]
    components: list[str]                   # Labels to apply
    reproduction_steps: Optional[str]       # Extracted steps
    confidence: float                       # LLM confidence score
    is_feature_request: bool                # Not a bug
    multiple_issues_detected: bool          # Report contains 2+ issues
    secondary_issues: list[str]             # Descriptions of secondary issues
    
    # ========== VALIDATION ==========
    validation_errors: Annotated[list[dict], operator.add]  # Accumulates
    retry_count: int                        # Current retry attempt
    used_premium_model: bool                # Escalation flag
    
    # ========== DUPLICATE DETECTION ==========
    duplicate_candidates: list[dict]        # Top-K similar issues
    is_duplicate: bool                      # Final determination
    duplicate_issue_id: Optional[int]       # Gitea issue number
    duplicate_confidence: float             # LLM comparison score
    
    # ========== OUTPUT ==========
    gitea_issue_url: Optional[str]          # Created/updated issue
    needs_human_review: bool                # Escalation flag
    processing_warnings: Annotated[list[str], operator.add]  # Accumulates
    
    # ========== AUDIT TRAIL ==========
    classification_history: Annotated[list[dict], operator.add]
    node_timings: Annotated[list[dict], operator.add]
