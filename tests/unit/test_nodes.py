"""
Unit tests for graph node functions
"""

import pytest

from src.graph.state import BugTriageState, create_initial_state
from src.graph.nodes.preprocess import preprocess_node
from src.graph.nodes.risk_check import risk_check_node
from src.graph.nodes.triage import route_confidence
from src.graph.nodes.validate import validate_node
from src.graph.workflow import build_graph, route_risk_level, route_duplicate


def _base_state(**overrides) -> BugTriageState:
    state = create_initial_state("test report", "test-thread")
    state.update(overrides)
    return state  # type: ignore[return-value]


def test_preprocess_strips_and_hashes():
    report = """Traceback (most recent call last):
  File "app.py", line 1, in <module>
    raise ValueError('fail')
ValueError: fail

Login broken on Safari."""
    state = _base_state(bug_report_text=report)
    result = preprocess_node(state)

    assert result["cleaned_report"] is not None
    assert "[STACK_TRACE_REMOVED]" in result["cleaned_report"]
    assert result["extracted_stacktrace"] is not None
    assert result["stacktrace_hash"] is not None
    assert len(result["stacktrace_hash"]) == 64


def test_risk_check_detects_security():
    state = _base_state(
        cleaned_report="found sql injection in login endpoint",
    )
    result = risk_check_node(state)

    assert result["risk_level"] == "escalate"
    assert "security_vulnerability" in result["risk_signals"]
    assert result["severity"] == "critical"
    assert result["confidence"] == 1.0


def test_risk_check_safe_path():
    state = _base_state(cleaned_report="button color is wrong on settings page")
    result = risk_check_node(state)

    assert result["risk_level"] == "safe"
    assert result["risk_signals"] == []


def test_confidence_gate_triggers_retry():
    state = _base_state(confidence=0.5, retry_count=1)
    assert route_confidence(state) == "premium_retry"


def test_confidence_gate_validates_high_confidence():
    state = _base_state(confidence=0.85, retry_count=0)
    assert route_confidence(state) == "validate"


def test_max_retries_fallback_route():
    state = _base_state(confidence=0.5, retry_count=3)
    assert route_confidence(state) == "duplicate_check"


def test_validate_passes_clean_extraction():
    state = _base_state(
        title="Login button unresponsive on mobile Safari",
        severity="high",
        components=["frontend"],
        cleaned_report="login broken on safari mobile",
        retry_count=0,
    )
    result = validate_node(state)
    assert result.get("validation_passed") is True


def test_validate_fallback_after_max_retries():
    state = _base_state(
        title="short",
        severity="critical",
        components=[],
        cleaned_report="api endpoint returns 500 when uploading large files",
        retry_count=2,
    )
    result = validate_node(state)

    assert result["severity"] == "medium"
    assert result["components"] == ["unknown"]
    assert result["needs_human_review"] is True
    assert result["validation_passed"] is True


def test_route_risk_escalates_to_human_review():
    state = _base_state(risk_level="escalate")
    assert route_risk_level(state) == "human_review"


def test_route_duplicate_to_comment():
    state = _base_state(is_duplicate=True, duplicate_issue_id=42)
    assert route_duplicate(state) == "comment_duplicate"


def test_graph_builds_and_compiles():
    graph = build_graph()
    compiled = graph.compile()
    assert compiled is not None


def test_validate_cosmetic_critical_mismatch():
    """B4 path: critical severity on cosmetic text downgrades to low."""
    state = _base_state(
        title="Footer copyright year incorrect",
        severity="critical",
        components=["frontend"],
        cleaned_report="footer copyright year still says 2024 instead of 2025",
        retry_count=0,
    )
    result = validate_node(state)
    assert result.get("validation_passed") is True
    assert result.get("severity") == "low"
