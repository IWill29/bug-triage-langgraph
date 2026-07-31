"""
API request/response models
Pydantic schemas for FastAPI endpoints
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal

from src.utils.input_safety import MAX_REPORT_LENGTH


class TriageRequest(BaseModel):
    """
    Request body for POST /api/triage
    """
    
    report: str = Field(
        description="Raw bug report text",
        min_length=1,
        max_length=MAX_REPORT_LENGTH,
    )
    
    thread_id: Optional[str] = Field(
        default=None,
        description="Optional thread ID for resuming execution"
    )

    @field_validator("report")
    @classmethod
    def strip_and_reject_whitespace_only(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Report cannot be empty or whitespace only")
        return stripped


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
    reproduction_steps: Optional[str] = Field(
        default=None,
        description="Extracted reproduction steps, or null if none provided",
    )
