"""
API request/response models
Pydantic schemas for FastAPI endpoints
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class TriageRequest(BaseModel):
    """
    Request body for POST /api/triage
    """
    
    report: str = Field(
        description="Raw bug report text",
        min_length=1
    )
    
    thread_id: Optional[str] = Field(
        default=None,
        description="Optional thread ID for resuming execution"
    )


class TriageResponse(BaseModel):
    """
    Response body for POST /api/triage
    """
    
    status: Literal["created", "duplicate", "pending", "error"]
    thread_id: str
    issue_url: Optional[str]
    
    title: str
    severity: Literal["critical", "high", "medium", "low"]
    components: List[str]
    confidence: float
    
    is_duplicate: bool
    duplicate_issue_id: Optional[int] = None
    
    needs_human_review: bool
    warnings: List[str] = Field(default_factory=list)
