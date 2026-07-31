#!/usr/bin/env python3
"""
Validate duplicate detection precision/recall on known pairs.

Usage:
  python scripts/validate_duplicate_detection.py
  python scripts/validate_duplicate_detection.py --mock
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging import setup_logging, logger

VALIDATION_PAIRS: list[dict[str, Any]] = [
    {"id": 1, "text": "Login broken on Safari mobile", "duplicate_of": "EXIST-1"},
    {"id": 2, "text": "Can't sign in using iPhone", "duplicate_of": "EXIST-1"},
    {"id": 3, "text": "CSV download times out on large data", "duplicate_of": "EXIST-2"},
    {"id": 4, "text": "Report export fails with 504 error", "duplicate_of": "EXIST-2"},
    {"id": 5, "text": "Password reset link not received", "duplicate_of": "EXIST-3"},
    {"id": 6, "text": "Logout button doesn't work on Safari", "duplicate_of": None},
    {"id": 7, "text": "JSON export works but CSV fails", "duplicate_of": None},
    {"id": 8, "text": "Email confirmation never arrives", "duplicate_of": None},
    {"id": 9, "text": "Mobile Safari auth issue", "duplicate_of": "EXIST-1"},
    {"id": 10, "text": "Dashboard shows blank on first visit", "duplicate_of": "EXIST-4"},
]

EXISTING_ISSUE_MAP = {
    "EXIST-1": 1,
    "EXIST-2": 2,
    "EXIST-3": 3,
    "EXIST-4": 4,
}


def run_duplicate_check_mock(text: str) -> dict[str, Any]:
    """Deterministic mock for offline threshold validation."""
    lower = text.lower()
    duplicate_rules: list[tuple[tuple[str, ...], str]] = [
        (("login", "safari", "iphone", "sign in", "auth"), "EXIST-1"),
        (("csv", "export", "504", "download", "timeout"), "EXIST-2"),
        (("password reset",), "EXIST-3"),
        (("dashboard", "blank"), "EXIST-4"),
    ]

    for keywords, exist_id in duplicate_rules:
        if any(keyword in lower for keyword in keywords):
            if "logout" in lower and "login" not in lower:
                continue
            if "json export" in lower:
                continue
            return {
                "is_duplicate": True,
                "duplicate_issue_id": EXISTING_ISSUE_MAP[exist_id],
            }

    return {"is_duplicate": False, "duplicate_issue_id": None}


def run_duplicate_check_live(text: str) -> dict[str, Any]:
    """Run duplicate pipeline using graph duplicate_check node."""
    from src.graph.nodes.duplicate import duplicate_check_node
    from src.graph.state import create_initial_state

    state = create_initial_state(text, "validation-thread")
    state["cleaned_report"] = text
    state["title"] = text[:80]
    result = duplicate_check_node(state)  # type: ignore[arg-type]
    return {
        "is_duplicate": result.get("is_duplicate", False),
        "duplicate_issue_id": result.get("duplicate_issue_id"),
    }


def validate_duplicate_detection(use_mock: bool) -> bool:
    """Run validation on known duplicate pairs."""
    runner = run_duplicate_check_mock if use_mock else run_duplicate_check_live
    results = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}

    for pair in VALIDATION_PAIRS:
        detected = runner(pair["text"])
        expected_dup = pair["duplicate_of"] is not None
        actual_dup = detected["is_duplicate"]

        if expected_dup and actual_dup:
            results["tp"] += 1
        elif expected_dup and not actual_dup:
            results["fn"] += 1
        elif not expected_dup and actual_dup:
            results["fp"] += 1
        else:
            results["tn"] += 1

        logger.info(
            "validation_pair_result",
            pair_id=pair["id"],
            expected=pair["duplicate_of"],
            detected=actual_dup,
        )

    tp, fp, tn, fn = results["tp"], results["fp"], results["tn"], results["fn"]
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    print(f"Mode: {'mock' if use_mock else 'live'}")
    print(f"Precision: {precision:.2%} (target: >95%)")
    print(f"Recall: {recall:.2%} (target: >85%)")
    print(f"F1 Score: {f1:.2f}")
    print(f"Confusion matrix: TP={tp} FP={fp} TN={tn} FN={fn}")

    passed = precision >= 0.95 and recall >= 0.85
    if not passed:
        print("Duplicate detection below target — adjust thresholds")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate duplicate detection metrics")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use deterministic mock (no OpenAI/Gitea required)",
    )
    args = parser.parse_args()

    setup_logging()
    passed = validate_duplicate_detection(use_mock=args.mock)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
