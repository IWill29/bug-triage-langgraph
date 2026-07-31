"""
Integration tests for LangGraph workflow routing and graph flow.
Uses mocked LLM/Gitea — no Docker or API keys required.
"""

from __future__ import annotations

from src.models.triage import TriageExtraction
from tests.fixtures.graph_helpers import invoke_graph, mock_gitea_issue_created


def test_low_confidence_triggers_premium_retry(mocker):
    """Low fast-model confidence routes through premium retry."""
    fast_extraction = TriageExtraction(
        title="Unclear bug report needs review",
        severity="medium",
        components=["unknown"],
        reproduction_steps=None,
        confidence=0.4,
        reasoning="Report lacks detail.",
    )
    premium_extraction = TriageExtraction(
        title="Login button unresponsive on mobile Safari",
        severity="high",
        components=["frontend"],
        reproduction_steps="Tap login on iPhone Safari; no response.",
        confidence=0.9,
        reasoning="Premium retry clarified mobile login issue.",
    )

    mocker.patch(
        "src.graph.nodes.triage.llm_service.invoke_fast",
        return_value=fast_extraction,
    )
    mocker.patch(
        "src.graph.nodes.triage.llm_service.invoke_premium",
        return_value=premium_extraction,
    )
    mocker.patch(
        "src.graph.nodes.duplicate.gitea_service.list_issues_sync",
        return_value=[],
    )
    mock_gitea_issue_created(mocker)

    result = invoke_graph("login thing broken maybe", "workflow-premium-retry")

    assert result["used_premium_model"] is True
    assert result["confidence"] >= 0.7
    assert result["retry_count"] == 1
    assert len(result["classification_history"]) >= 2
    assert result.get("gitea_issue_url") is not None


def test_duplicate_detection_prevents_new_issue(mocker):
    """Confirmed duplicate routes to comment_duplicate instead of create_bug."""
    extraction = TriageExtraction(
        title="Mobile Safari login button unresponsive",
        severity="high",
        components=["frontend", "auth"],
        reproduction_steps="Tap login on iPhone; nothing happens.",
        confidence=0.87,
        reasoning="Clear mobile login failure.",
    )

    mocker.patch(
        "src.graph.nodes.triage.llm_service.invoke_fast",
        return_value=extraction,
    )
    mocker.patch(
        "src.graph.nodes.duplicate.gitea_service.list_issues_sync",
        return_value=[{
            "number": 42,
            "title": "Login broken on mobile Safari",
            "body": "Safari login button not working",
        }],
    )
    mocker.patch(
        "src.graph.nodes.duplicate.embedding_service.generate_embedding",
        return_value=[0.1] * 8,
    )
    mocker.patch(
        "src.graph.nodes.duplicate.embedding_service.cosine_similarity",
        return_value=0.9,
    )
    from src.models.triage import DuplicateComparison

    mocker.patch(
        "src.graph.nodes.duplicate.llm_service.invoke_fast",
        return_value=DuplicateComparison(
            is_duplicate=True,
            confidence=0.95,
            reasoning="Same mobile Safari login bug.",
        ),
    )
    create_mock = mock_gitea_issue_created(mocker)
    comment_mock = mocker.patch(
        "src.graph.nodes.gitea.gitea_service.add_comment_sync",
        return_value={"id": 1},
    )

    result = invoke_graph(
        "Can't log in on iPhone Safari — login button does nothing",
        "workflow-dup",
    )

    assert result["is_duplicate"] is True
    assert result["duplicate_issue_id"] == 42
    assert "/issues/42" in result["gitea_issue_url"]
    create_mock.assert_not_called()
    comment_mock.assert_called_once()


def test_security_bypass_skips_ml_triage(mocker):
    """Security escalation skips fast_triage and routes to human_review."""
    fast_mock = mocker.patch(
        "src.graph.nodes.triage.llm_service.invoke_fast",
        side_effect=AssertionError("fast_triage must not run for security reports"),
    )

    result = invoke_graph(
        "Found SQL injection vulnerability in /api/users endpoint",
        "workflow-security",
    )

    fast_mock.assert_not_called()
    assert result["severity"] == "critical"
    assert result["confidence"] == 1.0
    assert result["needs_human_review"] is True
    assert result["risk_level"] == "escalate"


def test_feature_request_creates_enhancement_issue(mocker):
    """Feature requests route to create_feature node."""
    extraction = TriageExtraction(
        title="Add PDF export option for customer reports",
        severity="low",
        components=["frontend", "backend"],
        reproduction_steps=None,
        confidence=0.9,
        reasoning="Enhancement request, not a defect.",
        is_feature_request=True,
    )

    mocker.patch(
        "src.graph.nodes.triage.llm_service.invoke_fast",
        return_value=extraction,
    )
    mocker.patch(
        "src.graph.nodes.duplicate.gitea_service.list_issues_sync",
        return_value=[],
    )
    create_mock = mock_gitea_issue_created(mocker, issue_number=55)

    result = invoke_graph(
        "It would be nice to export reports to PDF as well as CSV.",
        "workflow-feature",
    )

    assert result["is_feature_request"] is True
    create_mock.assert_called_once()
    labels = create_mock.call_args.kwargs.get("labels") or create_mock.call_args[1].get("labels")
    assert "enhancement" in labels
    assert result.get("gitea_issue_url") is not None


def test_b8_stacktrace_hash_extracted(mocker):
    """Noisy log report extracts stacktrace during preprocess."""
    extraction = TriageExtraction(
        title="Checkout fails with NullReferenceException in OrderService",
        severity="high",
        components=["backend"],
        reproduction_steps="Complete checkout; 500 error in logs.",
        confidence=0.86,
        reasoning="Stack trace identifies OrderService.Calculate.",
    )

    mocker.patch(
        "src.graph.nodes.triage.llm_service.invoke_fast",
        return_value=extraction,
    )
    mocker.patch(
        "src.graph.nodes.duplicate.gitea_service.list_issues_sync",
        return_value=[],
    )
    mock_gitea_issue_created(mocker)

    report = """hey so this happened again
```
[2025-06-01 09:14:23] ERROR NullReferenceException in OrderService.Calculate() line 214
```
basically checkout dies sometimes"""

    result = invoke_graph(report, "workflow-b8-stacktrace")

    assert result["stacktrace_hash"] is not None
    assert len(result["stacktrace_hash"]) == 64
    assert result["severity"] == "high"
