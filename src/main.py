"""
FastAPI application entry point
"""

import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from src.config import settings
from src.utils.logging import setup_logging, logger
from src.utils.observability import configure_langsmith
from src.middleware.rate_limit import RateLimitMiddleware
from src.models.api import TriageRequest, TriageResponse
from src.graph.workflow import build_graph
from src.graph.checkpointer import setup_checkpointer, close_checkpointer
from src.graph.state import create_initial_state


setup_logging()
configure_langsmith(settings)

_compiled_graph = None
_checkpointer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, cleanup on shutdown."""
    global _compiled_graph, _checkpointer

    logger.info(
        "service_startup",
        environment=settings.environment,
        gitea_url=settings.gitea_url,
    )

    _checkpointer = setup_checkpointer()
    _compiled_graph = build_graph().compile(checkpointer=_checkpointer)

    logger.info("services_ready")

    yield

    if _checkpointer is not None and hasattr(_checkpointer, "close"):
        _checkpointer.close()
    close_checkpointer()
    logger.info("service_shutdown")


app = FastAPI(
    title="Bug Report Triage Service",
    description="LangGraph-based automated issue triage system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)


def _build_response(result: dict, thread_id: str) -> TriageResponse:
    """Map graph result state to API response."""
    if result.get("is_duplicate"):
        status = "duplicate"
    elif result.get("gitea_issue_url"):
        status = "created"
    elif result.get("needs_human_review"):
        status = "pending"
    else:
        status = "pending"

    return TriageResponse(
        status=status,
        thread_id=thread_id,
        issue_url=result.get("gitea_issue_url"),
        title=result.get("title") or "Untitled",
        severity=result.get("severity") or "medium",
        components=result.get("components") or ["unknown"],
        confidence=result.get("confidence", 0.0),
        is_duplicate=result.get("is_duplicate", False),
        duplicate_issue_id=result.get("duplicate_issue_id"),
        needs_human_review=result.get("needs_human_review", False),
        warnings=list(result.get("processing_warnings") or []),
    )


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {
        "status": "healthy",
        "service": "bug-triage",
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "service": "Bug Report Triage Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.post("/api/triage", response_model=TriageResponse)
async def triage_bug_report(request: TriageRequest) -> TriageResponse:
    """
    Triage a bug report through the LangGraph workflow.
    """
    if _compiled_graph is None:
        raise HTTPException(status_code=503, detail="Workflow not initialized")

    thread_id = request.thread_id or str(uuid.uuid4())

    logger.info(
        "triage_request_received",
        report_length=len(request.report),
        thread_id=thread_id,
    )

    try:
        initial_state = create_initial_state(
            bug_report_text=request.report,
            thread_id=thread_id,
        )
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 50,
        }

        # PostgresSaver is sync-only; sync nodes use invoke (not ainvoke).
        result = await asyncio.to_thread(
            _compiled_graph.invoke, initial_state, config
        )

        response = _build_response(result, thread_id)

        logger.info(
            "triage_complete",
            thread_id=thread_id,
            status=response.status,
            is_duplicate=response.is_duplicate,
        )

        return response

    except Exception as exc:
        logger.error(
            "triage_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            thread_id=thread_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Triage processing failed: {str(exc)}",
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower(),
    )
