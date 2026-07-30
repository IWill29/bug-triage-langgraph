"""
Pytest configuration and fixtures
"""

import pytest
from typing import Generator
from langgraph.checkpoint.memory import MemorySaver

from src.graph.workflow import build_graph


@pytest.fixture
def compiled_graph():
    """
    Reusable graph fixture with in-memory checkpointer
    Use for integration tests
    """
    graph = build_graph()
    return graph.compile(checkpointer=MemorySaver())


@pytest.fixture
def sample_bug_report() -> str:
    """Simple bug report for testing"""
    return """When I upload a profile picture larger than about 5MB, 
    the page shows a spinner forever and the picture never saves. 
    Tried it with a 8MB PNG and a 12MB JPEG, same result. 
    Chrome on Windows. Smaller images work fine."""


@pytest.fixture
def vague_bug_report() -> str:
    """Vague bug report (should trigger low confidence)"""
    return "the reports thing is broken again pls fix"


@pytest.fixture
def security_bug_report() -> str:
    """Security issue (should trigger escalation)"""
    return "Found SQL injection vulnerability in /api/users endpoint"


@pytest.fixture
def duplicate_bug_report() -> str:
    """Duplicate of EXIST-1"""
    return """I can't log in on my iPhone. I open the app in Safari, 
    type my details, tap the login button and literally nothing happens. 
    My colleague has the same problem on her phone."""


@pytest.fixture
def feature_request() -> str:
    """Feature request (not a bug)"""
    return """It would be really nice if we could export reports to PDF 
    as well as CSV. A lot of our customers ask for this."""
