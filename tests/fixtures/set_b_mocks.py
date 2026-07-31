"""
Deterministic mock LLM responses for Set B integration tests.
Maps sample IDs to TriageExtraction payloads — no live API keys required.
"""

from __future__ import annotations

from src.models.triage import DuplicateComparison, TriageExtraction

# Gitea EXIST-1 issue used for B5 duplicate detection
EXIST_1_ISSUE = {
    "number": 1,
    "title": "Login button unresponsive on mobile Safari",
    "body": "Users cannot log in on iPhone Safari. Tap login — nothing happens.",
}


def triage_extraction_for_sample(sample_id: str, *, premium: bool = False) -> TriageExtraction:
    """Return mock TriageExtraction for a Set B sample key."""
    builders: dict[str, dict] = {
        "B1_clean": {
            "title": "Profile picture upload hangs on files over 5MB",
            "severity": "medium",
            "components": ["frontend", "backend"],
            "reproduction_steps": "Upload PNG/JPEG >5MB in Chrome on Windows; spinner runs forever.",
            "confidence": 0.88,
            "reasoning": "Clear repro steps, file size threshold, browser context.",
        },
        "B2_api_error": {
            "title": "Orders API returns 500 when status param omitted",
            "severity": "high",
            "components": ["api", "backend"],
            "reproduction_steps": "curl /api/v2/orders without status; add status=open to succeed.",
            "confidence": 0.91,
            "reasoning": "API endpoint, 500 error, curl repro provided.",
        },
        "B3_vague": {
            "title": "Reports feature malfunctioning",
            "severity": "medium",
            "components": ["unknown"],
            "reproduction_steps": None,
            "confidence": 0.45 if not premium else 0.55,
            "reasoning": "Underspecified report; limited actionable detail.",
        },
        "B4_cosmetic_urgent": {
            "title": "Footer copyright year shows 2024 instead of 2025",
            "severity": "critical" if not premium else "low",
            "components": ["frontend"],
            "reproduction_steps": "View site footer; copyright year still 2024.",
            "confidence": 0.82 if not premium else 0.85,
            "reasoning": "Cosmetic footer typo; urgency tone does not imply critical severity."
            if premium
            else "User marked URGENT; initial pass over-weighted tone.",
        },
        "B5_duplicate": {
            "title": "Mobile Safari login button unresponsive",
            "severity": "high",
            "components": ["frontend", "auth"],
            "reproduction_steps": "Open app in Safari on iPhone, enter credentials, tap login.",
            "confidence": 0.87,
            "reasoning": "Mobile login failure matches known EXIST-1 pattern.",
        },
        "B6_feature": {
            "title": "Add PDF export option for reports",
            "severity": "low",
            "components": ["frontend", "backend"],
            "reproduction_steps": None,
            "confidence": 0.90,
            "reasoning": "Enhancement request, not a defect.",
            "is_feature_request": True,
        },
        "B7_multiple": {
            "title": "Search returns no results for exact matches",
            "severity": "medium",
            "components": ["frontend"],
            "reproduction_steps": "Search exact title; empty results. Also date picker allows end before start.",
            "confidence": 0.83,
            "reasoning": "Primary search bug; secondary date picker and mobile menu issues noted.",
            "multiple_issues_detected": True,
            "secondary_issues": [
                "Date picker allows end date before start date",
                "Mobile menu overlaps header on small screens",
            ],
        },
        "B8_noisy": {
            "title": "Checkout fails with NullReferenceException in OrderService",
            "severity": "high",
            "components": ["backend"],
            "reproduction_steps": "Complete checkout; intermittent 500 with NullReferenceException in logs.",
            "confidence": 0.86,
            "reasoning": "Stack trace points to OrderService.Calculate line 214.",
        },
    }

    data = builders[sample_id].copy()
    is_feature = data.pop("is_feature_request", False)
    multiple = data.pop("multiple_issues_detected", False)
    secondary = data.pop("secondary_issues", [])

    return TriageExtraction(
        is_feature_request=is_feature,
        multiple_issues_detected=multiple,
        secondary_issues=secondary,
        **data,
    )


def duplicate_comparison_confirm() -> DuplicateComparison:
    """Mock LLM confirming duplicate for B5."""
    return DuplicateComparison(
        is_duplicate=True,
        confidence=0.92,
        reasoning="Same mobile Safari login failure as EXIST-1.",
    )


def duplicate_comparison_reject() -> DuplicateComparison:
    """Mock LLM rejecting duplicate for non-B5 samples."""
    return DuplicateComparison(
        is_duplicate=False,
        confidence=0.35,
        reasoning="Related topic but distinct bug report.",
    )
