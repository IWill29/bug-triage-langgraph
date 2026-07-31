#!/usr/bin/env python3
"""
Set B validation harness — run all sample reports through triage workflow.

Usage:
  python scripts/run_set_b.py              # mocked LLM (no API keys)
  python scripts/run_set_b.py --live       # live LLM + Gitea (requires Docker/keys)
  python scripts/run_set_b.py --sample B3  # single sample
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from langgraph.checkpoint.memory import MemorySaver

from src.graph.state import create_initial_state
from src.graph.workflow import build_graph
from src.utils.logging import setup_logging, logger
from tests.fixtures.sample_reports import SAMPLE_REPORTS

# QA gate samples: B1 + B3–B8 (7 functional tests per qa-tester agent)
SET_B_QA_SAMPLES = [
    "B1_clean",
    "B3_vague",
    "B4_cosmetic_urgent",
    "B5_duplicate",
    "B6_feature",
    "B7_multiple",
    "B8_noisy",
]


def validate_result(sample_id: str, result: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check result against expected behavior for a Set B sample."""
    expected = SAMPLE_REPORTS[sample_id]["expected"]
    failures: list[str] = []

    if sample_id == "B3_vague":
        if result.get("confidence", 1.0) >= 0.7:
            failures.append("confidence should be < 0.70")
        if not result.get("needs_human_review"):
            failures.append("needs_human_review should be True")
    elif sample_id == "B4_cosmetic_urgent":
        if result.get("severity") != "low":
            failures.append(f"severity should be low, got {result.get('severity')}")
    elif sample_id == "B5_duplicate":
        if not result.get("is_duplicate"):
            failures.append("should detect duplicate of EXIST-1")
    elif sample_id == "B6_feature":
        if not result.get("is_feature_request"):
            failures.append("should flag feature request")
    elif sample_id == "B7_multiple":
        if not result.get("multiple_issues_detected"):
            failures.append("should detect multiple issues")
    elif sample_id == "B8_noisy":
        if not result.get("stacktrace_hash"):
            failures.append("should extract stacktrace hash")
        if result.get("severity") != expected.get("severity"):
            failures.append(f"severity should be {expected.get('severity')}")
    else:
        if expected.get("severity") and result.get("severity") != expected["severity"]:
            failures.append(
                f"severity should be {expected['severity']}, got {result.get('severity')}"
            )
        if expected.get("has_repro") and not result.get("reproduction_steps"):
            failures.append("reproduction steps expected")

    if not result.get("gitea_issue_url") and not result.get("input_rejected"):
        if sample_id != "B5_duplicate" or not result.get("is_duplicate"):
            failures.append("expected gitea_issue_url or duplicate link")

    return len(failures) == 0, failures


def run_sample(sample_id: str, *, live: bool) -> dict[str, Any]:
    """Execute triage for one Set B sample."""
    from contextlib import ExitStack
    from unittest.mock import patch

    from tests.fixtures.graph_helpers import install_set_b_mocks

    report = SAMPLE_REPORTS[sample_id]["text"]
    thread_id = str(uuid.uuid4())

    graph = build_graph().compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    initial = create_initial_state(report, thread_id)

    if live:
        return graph.invoke(initial, config)

    class _Mocker:
        def __init__(self, stack: ExitStack) -> None:
            self._stack = stack

        def patch(self, target: str, **kwargs: Any):
            return self._stack.enter_context(patch(target, **kwargs))

    with ExitStack() as stack:
        install_set_b_mocks(
            _Mocker(stack),
            confirm_duplicate=(sample_id == "B5_duplicate"),
        )
        return graph.invoke(initial, config)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Set B validation harness")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live LLM/Gitea (requires OPENAI_API_KEY, Docker, GITEA_TOKEN)",
    )
    parser.add_argument(
        "--sample",
        choices=list(SAMPLE_REPORTS.keys()),
        help="Run a single sample only",
    )
    args = parser.parse_args()

    setup_logging()
    samples = [args.sample] if args.sample else SET_B_QA_SAMPLES

    passed = 0
    total = len(samples)

    print(f"\nSet B Validation — mode: {'live' if args.live else 'mocked'}\n")
    print("-" * 60)

    for sample_id in samples:
        try:
            result = run_sample(sample_id, live=args.live)
            ok, failures = validate_result(sample_id, result)
            status = "PASS" if ok else "FAIL"
            print(f"{sample_id}: {status}")
            if failures:
                for failure in failures:
                    print(f"  - {failure}")
            if ok:
                passed += 1
            logger.info(
                "set_b_sample_result",
                sample_id=sample_id,
                status=status,
                severity=result.get("severity"),
                confidence=result.get("confidence"),
            )
        except Exception as exc:
            print(f"{sample_id}: ERROR — {type(exc).__name__}: {exc}")
            logger.error("set_b_sample_error", sample_id=sample_id, error=str(exc))

    print("-" * 60)
    print(f"Score: {passed}/{total}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
