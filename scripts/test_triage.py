#!/usr/bin/env python3
"""
CLI test harness for triage service.
Runs the LangGraph workflow locally with an in-memory checkpointer.
Requires OPENAI_API_KEY (and optionally GITEA_* for issue creation).
"""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langgraph.checkpoint.memory import MemorySaver

from src.graph.workflow import build_graph
from src.graph.state import create_initial_state
from src.utils.logging import setup_logging, logger


async def test_triage(report: str) -> dict:
    """Run triage workflow with a bug report and print results."""
    setup_logging()

    thread_id = str(uuid.uuid4())
    logger.info("test_triage_start", report_length=len(report), thread_id=thread_id)

    graph = build_graph().compile(checkpointer=MemorySaver())
    initial_state = create_initial_state(bug_report_text=report, thread_id=thread_id)
    config = {"configurable": {"thread_id": thread_id}}

    result = await graph.ainvoke(initial_state, config)

    print(f"\n{'=' * 60}")
    print("Bug Report Triage Test")
    print(f"{'=' * 60}\n")
    print(f"Thread ID: {thread_id}")
    print(f"Title: {result.get('title', 'N/A')}")
    print(f"Severity: {result.get('severity', 'N/A')}")
    print(f"Components: {result.get('components', [])}")
    print(f"Confidence: {result.get('confidence', 0.0):.2f}")
    print(f"Needs human review: {result.get('needs_human_review', False)}")
    print(f"Is duplicate: {result.get('is_duplicate', False)}")
    if result.get("gitea_issue_url"):
        print(f"Issue URL: {result['gitea_issue_url']}")
    if result.get("processing_warnings"):
        print(f"Warnings: {result['processing_warnings']}")
    print(f"\n{'=' * 60}\n")

    return result


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_triage.py 'bug report text'")
        print("\nExample:")
        print('  python scripts/test_triage.py "Login button not working"')
        print("\nRequires OPENAI_API_KEY in environment or .env file.")
        sys.exit(1)

    report = sys.argv[1]
    asyncio.run(test_triage(report))


if __name__ == "__main__":
    main()
