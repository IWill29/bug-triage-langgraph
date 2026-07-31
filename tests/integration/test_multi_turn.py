"""
Multi-turn and HITL integration tests — state accumulation and interrupt/resume.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from src.graph.state import create_initial_state
from src.graph.workflow import build_graph
from src.models.triage import TriageExtraction


def test_classification_history_accumulates_on_premium_retry(mocker):
    """Premium retry appends to classification_history within single invoke."""
    fast_extraction = TriageExtraction(
        title="Vague reports feature issue",
        severity="medium",
        components=["unknown"],
        reproduction_steps=None,
        confidence=0.42,
        reasoning="Underspecified.",
    )
    premium_extraction = TriageExtraction(
        title="Reports dashboard fails intermittently",
        severity="medium",
        components=["frontend"],
        reproduction_steps=None,
        confidence=0.78,
        reasoning="Premium pass added context.",
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
    mocker.patch(
        "src.graph.nodes.gitea.gitea_service.create_issue_sync",
        return_value={"number": 10, "html_url": "http://localhost:3000/issues/10"},
    )

    graph = build_graph().compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "multi-turn-history"}, "recursion_limit": 50}
    result = graph.invoke(
        create_initial_state("the reports thing is broken again pls fix", "multi-turn-history"),
        config,
    )

    assert len(result["classification_history"]) >= 2
    models = [entry["model"] for entry in result["classification_history"]]
    assert any("mini" in m for m in models)
    assert any("gpt-4o" in m for m in models)
    assert result["retry_count"] == 1


def test_interrupt_before_create_bug(mocker):
    """HITL: graph pauses before create_bug; resume completes issue creation."""
    extraction = TriageExtraction(
        title="Settings page save button unresponsive",
        severity="medium",
        components=["frontend"],
        reproduction_steps="Open settings, change value, click save — no response.",
        confidence=0.88,
        reasoning="Clear UI bug with repro.",
    )

    mocker.patch(
        "src.graph.nodes.triage.llm_service.invoke_fast",
        return_value=extraction,
    )
    mocker.patch(
        "src.graph.nodes.duplicate.gitea_service.list_issues_sync",
        return_value=[],
    )
    create_mock = mocker.patch(
        "src.graph.nodes.gitea.gitea_service.create_issue_sync",
        return_value={"number": 77, "html_url": "http://localhost:3000/issues/77"},
    )

    graph = build_graph()
    app = graph.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["create_bug"],
    )

    config = {"configurable": {"thread_id": "hitl-interrupt"}, "recursion_limit": 50}
    initial = create_initial_state("Save button on settings page does not work", "hitl-interrupt")

    paused = app.invoke(initial, config)
    state = app.get_state(config)

    assert state.next == ("create_bug",)
    assert paused.get("gitea_issue_url") is None
    create_mock.assert_not_called()

    final = app.invoke(None, config)

    assert final.get("gitea_issue_url") == "http://localhost:3000/issues/77"
    create_mock.assert_called_once()


def test_checkpoint_preserves_state_across_resume(mocker):
    """State fields persist when resuming from interrupt."""
    extraction = TriageExtraction(
        title="Export CSV timeout on large datasets",
        severity="high",
        components=["backend"],
        reproduction_steps="Export >10k rows; request times out.",
        confidence=0.9,
        reasoning="Performance issue with clear repro.",
    )

    mocker.patch(
        "src.graph.nodes.triage.llm_service.invoke_fast",
        return_value=extraction,
    )
    mocker.patch(
        "src.graph.nodes.duplicate.gitea_service.list_issues_sync",
        return_value=[],
    )
    mocker.patch(
        "src.graph.nodes.gitea.gitea_service.create_issue_sync",
        return_value={"number": 88, "html_url": "http://localhost:3000/issues/88"},
    )

    app = build_graph().compile(
        checkpointer=MemorySaver(),
        interrupt_before=["create_bug"],
    )
    config = {"configurable": {"thread_id": "checkpoint-resume"}, "recursion_limit": 50}

    app.invoke(
        create_initial_state("CSV export times out on large data", "checkpoint-resume"),
        config,
    )
    mid_state = app.get_state(config)
    assert mid_state.values.get("title") == extraction.title
    assert mid_state.values.get("severity") == "high"

    final = app.invoke(None, config)
    assert final["title"] == extraction.title
    assert final.get("gitea_issue_url") is not None
