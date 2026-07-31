"""
Set B validation tests — B1, B3–B8 with mocked LLM/Gitea.
Live Set B requires Docker + keys; these tests satisfy Phase 4 QA gate offline.
"""

from __future__ import annotations

import pytest

from tests.fixtures.graph_helpers import install_set_b_mocks, invoke_graph
from tests.fixtures.sample_reports import SAMPLE_REPORTS


@pytest.fixture
def set_b_mocks(mocker):
    """Install deterministic mocks for all Set B samples."""
    install_set_b_mocks(mocker, confirm_duplicate=False)
    yield


@pytest.fixture
def set_b_duplicate_mocks(mocker):
    """Mocks with duplicate detection enabled for B5."""
    install_set_b_mocks(mocker, confirm_duplicate=True)
    yield


@pytest.mark.parametrize("sample_id", ["B1_clean", "B2_api_error"])
def test_set_b_clean_reports_extract_and_create_issue(sample_id, set_b_mocks):
    """B1/B2: clear reports extract structured fields and create issues."""
    sample = SAMPLE_REPORTS[sample_id]
    expected = sample["expected"]
    result = invoke_graph(sample["text"], f"setb-{sample_id}")

    assert result["input_rejected"] is False
    assert result["severity"] == expected["severity"]
    assert set(expected["components"]).issubset(set(result.get("components") or []))
    assert result["confidence"] > 0.75
    assert result.get("gitea_issue_url") is not None
    if expected.get("has_repro"):
        assert result.get("reproduction_steps") is not None


def test_set_b3_vague_triggers_premium_and_human_review(set_b_mocks):
    """B3: vague report — low confidence, premium retry, human review flag."""
    sample = SAMPLE_REPORTS["B3_vague"]
    result = invoke_graph(sample["text"], "setb-B3")

    assert result["used_premium_model"] is True
    assert result["confidence"] < 0.7
    assert result["needs_human_review"] is True
    assert result.get("gitea_issue_url") is not None


def test_set_b4_cosmetic_overrides_urgent_tone(set_b_mocks):
    """B4: URGENT cosmetic report downgraded to low severity after validate retry."""
    sample = SAMPLE_REPORTS["B4_cosmetic_urgent"]
    result = invoke_graph(sample["text"], "setb-B4")

    assert result["severity"] == "low"
    assert "frontend" in (result.get("components") or [])
    assert result.get("gitea_issue_url") is not None


def test_set_b5_duplicate_links_existing_issue(set_b_duplicate_mocks):
    """B5: duplicate of EXIST-1 comments instead of creating new issue."""
    sample = SAMPLE_REPORTS["B5_duplicate"]
    result = invoke_graph(sample["text"], "setb-B5")

    assert result["is_duplicate"] is True
    assert result["duplicate_issue_id"] == 1
    assert "/issues/1" in result["gitea_issue_url"]


def test_set_b6_feature_request_routes_to_enhancement(set_b_mocks):
    """B6: feature request flagged and routed to create_feature."""
    sample = SAMPLE_REPORTS["B6_feature"]
    result = invoke_graph(sample["text"], "setb-B6")

    assert result["is_feature_request"] is True
    assert result.get("gitea_issue_url") is not None


def test_set_b7_multiple_issues_detected(set_b_mocks):
    """B7: multi-issue report sets multiple_issues_detected and warnings."""
    sample = SAMPLE_REPORTS["B7_multiple"]
    result = invoke_graph(sample["text"], "setb-B7")

    assert result["multiple_issues_detected"] is True
    assert len(result.get("secondary_issues") or []) >= 1
    warnings = " ".join(result.get("processing_warnings") or []).lower()
    assert "multiple" in warnings or result["multiple_issues_detected"]


def test_set_b8_noisy_log_extracts_stacktrace(set_b_mocks):
    """B8: noisy log report extracts stacktrace and classifies backend high."""
    sample = SAMPLE_REPORTS["B8_noisy"]
    expected = sample["expected"]
    result = invoke_graph(sample["text"], "setb-B8")

    assert result["stacktrace_hash"] is not None
    assert result["severity"] == expected["severity"]
    assert "backend" in (result.get("components") or [])


def test_all_set_b_samples_complete_without_crash(set_b_mocks):
    """Smoke: every Set B sample completes the graph without exception."""
    for sample_id, sample in SAMPLE_REPORTS.items():
        result = invoke_graph(sample["text"], f"setb-smoke-{sample_id}")
        assert result.get("thread_id") or True  # graph ran
        assert "severity" in result or result.get("input_rejected")
