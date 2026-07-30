"""
FastAPI application entry point
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from typing import Optional
import os

from src.config import settings
from src.utils.logging import setup_logging, logger
from src.models.api import TriageRequest, TriageResponse


# Setup structured logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize services on startup, cleanup on shutdown
    """
    logger.info(
        "service_startup",
        environment=settings.environment,
        gitea_url=settings.gitea_url
    )
    
    # TODO: Initialize LangGraph checkpointer
    # TODO: Seed Gitea with Set A if needed
    
    logger.info("services_ready")
    
    yield
    
    logger.info("service_shutdown")


# Create FastAPI app
app = FastAPI(
    title="Bug Report Triage Service",
    description="LangGraph-based automated issue triage system",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    return {
        "status": "healthy",
        "service": "bug-triage",
        "version": "1.0.0"
    }


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "service": "Bug Report Triage Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.post("/api/triage", response_model=TriageResponse)
async def triage_bug_report(request: TriageRequest) -> TriageResponse:
    """
    Triage a bug report
    
    Processes raw bug report text through the LangGraph workflow:
    1. Preprocesses and cleans text
    2. Checks for risk/security issues
    3. Extracts structured information (title, severity, components)
    4. Validates output quality
    5. Checks for duplicates
    6. Creates Gitea issue or comments on duplicate
    
    Returns:
        TriageResponse with issue URL and triage metadata
    """
    logger.info(
        "triage_request_received",
        report_length=len(request.report),
        thread_id=request.thread_id
    )
    
    try:
        # TODO: Implement LangGraph workflow invocation
        # For now, return placeholder response
        
        return TriageResponse(
            status="pending",
            thread_id=request.thread_id or "generated-id",
            issue_url=None,
            title="TODO: Implement workflow",
            severity="medium",
            components=["unknown"],
            confidence=0.0,
            is_duplicate=False,
            needs_human_review=True,
            warnings=["Workflow not yet implemented"]
        )
        
    except Exception as e:
        logger.error(
            "triage_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Triage processing failed: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower()
    )
