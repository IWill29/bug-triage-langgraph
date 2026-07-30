"""
Triage models for LLM structured outputs
Pydantic schemas for extraction and validation
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional


class TriageExtraction(BaseModel):
    """
    Schema for LLM structured output during triage
    Used by fast_triage_node and premium_retry_node
    """
    
    title: str = Field(
        description="Concise bug title (5-10 words)",
        min_length=10,
        max_length=100
    )
    
    severity: Literal["critical", "high", "medium", "low"] = Field(
        description="Bug severity level"
    )
    
    components: list[Literal[
        "frontend", "backend", "api", "auth",
        "database", "infra", "docs", "unknown"
    ]] = Field(
        description="Affected system components",
        min_length=1
    )
    
    reproduction_steps: Optional[str] = Field(
        default=None,
        description="Clear steps to reproduce, or null if not provided"
    )
    
    confidence: float = Field(
        description="Confidence score 0.0-1.0",
        ge=0.0,
        le=1.0
    )
    
    reasoning: str = Field(
        description="Brief explanation of classification"
    )
    
    is_feature_request: bool = Field(
        default=False,
        description="True if this is a feature request, not a bug"
    )
    
    multiple_issues_detected: bool = Field(
        default=False,
        description="True if report contains multiple distinct issues"
    )
    
    secondary_issues: list[str] = Field(
        default_factory=list,
        description="Brief descriptions of secondary issues (if multiple detected)"
    )


class DuplicateComparison(BaseModel):
    """
    Schema for LLM duplicate comparison
    Used by duplicate_check_node
    """
    
    is_duplicate: bool = Field(
        description="True if reports describe the SAME bug (not just related)"
    )
    
    confidence: float = Field(
        description="Confidence score 0.0-1.0",
        ge=0.0,
        le=1.0
    )
    
    reasoning: str = Field(
        description="Brief explanation (1-2 sentences)"
    )
