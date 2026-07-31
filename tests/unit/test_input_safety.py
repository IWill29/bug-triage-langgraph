"""
Unit tests for input safety utilities
"""

from src.utils.input_safety import (
    MAX_REPORT_LENGTH,
    classify_input,
    sanitize_report,
)


def test_sanitize_truncates_long_report():
    text = "x" * (MAX_REPORT_LENGTH + 500)
    sanitized, warnings = sanitize_report(text)
    assert len(sanitized) == MAX_REPORT_LENGTH
    assert warnings


def test_sanitize_strips_script_tags():
    text = "Login error <script>alert(1)</script> on mobile"
    sanitized, warnings = sanitize_report(text)
    assert "<script>" not in sanitized
    assert "Login error" in sanitized
    assert warnings


def test_classify_too_short():
    assert classify_input("short") == "too_short"


def test_classify_off_topic_recipe():
    text = "Recipe: preheat oven to 350. Mix ingredients and bake 30 minutes."
    assert classify_input(text) == "off_topic"


def test_classify_valid_bug_report():
    text = "Login button fails with 500 error when uploading large files."
    assert classify_input(text) == "valid"
