"""
Shared helpers for integration tests — graph invoke and external-service mocks.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from langgraph.checkpoint.memory import MemorySaver

from src.graph.state import create_initial_state
from src.graph.workflow import build_graph
from src.models.triage import DuplicateComparison, TriageExtraction
from tests.fixtures.sample_reports import SAMPLE_REPORTS
from tests.fixtures.set_b_mocks import (
    EXIST_1_ISSUE,
    duplicate_comparison_confirm,
    duplicate_comparison_reject,
    triage_extraction_for_sample,
)


def invoke_graph(report: str, thread_id: str = "test-thread") -> dict:
    """Run full workflow with in-memory checkpointer."""
    graph = build_graph().compile(checkpointer=MemorySaver())
    initial = create_initial_state(report, thread_id)
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    return graph.invoke(initial, config)


def _resolve_sample_id(prompt: str) -> str | None:
    """Match prompt text to a Set B sample key."""
    normalized = " ".join(prompt.lower().split())
    for sample_id, sample in SAMPLE_REPORTS.items():
        sample_norm = " ".join(sample["text"].lower().split())
        if sample_norm[:40] in normalized or normalized[:40] in sample_norm:
            return sample_id
        # B3 is short — match by distinctive phrase
        if sample_id == "B3_vague" and "reports thing is broken" in normalized:
            return sample_id
    return None


def install_set_b_mocks(mocker: Any, *, confirm_duplicate: bool = False) -> None:
    """
    Patch LLM, Gitea, and embedding services for deterministic Set B runs.
    """
    def invoke_fast(prompt: str, schema: type) -> TriageExtraction | DuplicateComparison:
        if schema.__name__ == "DuplicateComparison":
            return duplicate_comparison_confirm() if confirm_duplicate else duplicate_comparison_reject()

        sample_id = _resolve_sample_id(prompt)
        if sample_id:
            return triage_extraction_for_sample(sample_id, premium=False)
        return triage_extraction_for_sample("B1_clean", premium=False)

    def invoke_premium(prompt: str, schema: type) -> TriageExtraction | DuplicateComparison:
        if schema.__name__ == "DuplicateComparison":
            return duplicate_comparison_confirm() if confirm_duplicate else duplicate_comparison_reject()

        sample_id = _resolve_sample_id(prompt)
        if sample_id:
            return triage_extraction_for_sample(sample_id, premium=True)
        return triage_extraction_for_sample("B3_vague", premium=True)

    mocker.patch(
        "src.graph.nodes.triage.llm_service.invoke_fast",
        side_effect=invoke_fast,
    )
    mocker.patch(
        "src.graph.nodes.triage.llm_service.invoke_premium",
        side_effect=invoke_premium,
    )
    mocker.patch(
        "src.graph.nodes.duplicate.llm_service.invoke_fast",
        side_effect=invoke_fast,
    )

    mocker.patch(
        "src.graph.nodes.duplicate.gitea_service.list_issues_sync",
        return_value=[EXIST_1_ISSUE],
    )
    mocker.patch(
        "src.graph.nodes.gitea.gitea_service.create_issue_sync",
        return_value={"number": 99, "html_url": "http://localhost:3000/issues/99"},
    )
    mocker.patch(
        "src.graph.nodes.gitea.gitea_service.add_comment_sync",
        return_value={"id": 1},
    )

    mocker.patch(
        "src.graph.nodes.duplicate.embedding_service.generate_embedding",
        return_value=[0.1] * 8,
    )
    mocker.patch(
        "src.graph.nodes.duplicate.embedding_service.cosine_similarity",
        return_value=0.85 if confirm_duplicate else 0.3,
    )


def mock_gitea_issue_created(mocker: Any, issue_number: int = 99) -> MagicMock:
    """Patch Gitea create_issue_sync and return the mock."""
    return mocker.patch(
        "src.graph.nodes.gitea.gitea_service.create_issue_sync",
        return_value={
            "number": issue_number,
            "html_url": f"http://localhost:3000/issues/{issue_number}",
        },
    )
