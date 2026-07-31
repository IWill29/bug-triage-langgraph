"""
Input safety utilities for hostile, empty, and off-topic reports.
"""

from __future__ import annotations

import re
from typing import Literal

MAX_REPORT_LENGTH = 10_000

PROMPT_INJECTION_PATTERNS: tuple[str, ...] = (
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?prior",
    r"you\s+are\s+now\s+a",
    r"system\s+prompt",
    r"<\s*script",
    r"javascript:",
    r"onerror\s*=",
    r";\s*drop\s+table",
    r";\s*delete\s+from",
    r"union\s+select",
)

OFF_TOPIC_PATTERNS: tuple[str, ...] = (
    r"\brecipe\b",
    r"\bingredients\b",
    r"\bpreheat oven\b",
    r"\bpoem\b",
    r"\broses are red\b",
    r"\bweather forecast\b",
)

BUG_INDICATOR_KEYWORDS: frozenset[str] = frozenset({
    "bug",
    "error",
    "broken",
    "fail",
    "crash",
    "issue",
    "exception",
    "login",
    "logout",
    "upload",
    "download",
    "timeout",
    "500",
    "404",
    "fix",
    "report",
    "vulnerability",
    "injection",
    "xss",
    "sql",
})


InputQuality = Literal["valid", "off_topic", "too_short", "hostile"]


def sanitize_report(text: str) -> tuple[str, list[str]]:
    """
    Strip hostile patterns and enforce length limits.

    Returns sanitized text and non-fatal warnings.
    """
    warnings: list[str] = []

    if len(text) > MAX_REPORT_LENGTH:
        text = text[:MAX_REPORT_LENGTH]
        warnings.append(f"Report truncated to {MAX_REPORT_LENGTH} characters")

    text = re.sub(
        r"<script[^>]*>.*?</script>",
        "[SCRIPT_REMOVED]",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if "[SCRIPT_REMOVED]" in text:
        warnings.append("Script content removed from report")
    text = re.sub(r"<[^>]+>", "", text)

    hostile_hits = 0
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            hostile_hits += 1
            text = re.sub(pattern, "[REDACTED]", text, flags=re.IGNORECASE)

    if hostile_hits:
        warnings.append(
            f"Potential hostile input neutralized ({hostile_hits} pattern(s))"
        )

    return text.strip(), warnings


def classify_input(text: str) -> InputQuality:
    """Classify cleaned report quality before LLM processing."""
    cleaned = text.strip()
    if len(cleaned) < 10:
        return "too_short"

    lower = cleaned.lower()
    hostile_score = sum(
        1 for pattern in PROMPT_INJECTION_PATTERNS
        if re.search(pattern, lower, re.IGNORECASE)
    )
    if hostile_score >= 2 and not _has_bug_indicators(lower):
        return "hostile"

    if any(re.search(pattern, lower) for pattern in OFF_TOPIC_PATTERNS):
        if not _has_bug_indicators(lower):
            return "off_topic"

    if not _has_bug_indicators(lower) and len(cleaned.split()) < 6:
        return "off_topic"

    return "valid"


def _has_bug_indicators(text: str) -> bool:
    return any(keyword in text for keyword in BUG_INDICATOR_KEYWORDS)
