"""
Unit tests for text utilities
"""

from src.utils.text_utils import (
    detect_pii,
    preprocess_report,
    strip_email_signatures,
)


def test_strip_email_signature():
    text = "Bug report here.\n\nSent from my iPhone"
    cleaned = strip_email_signatures(text)
    assert "Sent from my iPhone" not in cleaned
    assert "Bug report here" in cleaned


def test_detect_pii_email():
    assert detect_pii("contact me at user@example.com") is True


def test_detect_pii_clean_text():
    assert detect_pii("login button does not respond") is False


def test_preprocess_pipeline():
    text = "  Multiple   spaces   and\n\n\n\nextra newlines  "
    cleaned, stacktrace, stacktrace_hash = preprocess_report(text)
    assert stacktrace is None
    assert stacktrace_hash is None
    assert "  " not in cleaned or cleaned.count("  ") == 0


def test_preprocess_extracts_log_style_error():
    text = """hey checkout fails
```
[2025-06-01 09:14:23] ERROR NullReferenceException in OrderService.Calculate() line 214
```
sometimes"""
    cleaned, stacktrace, stacktrace_hash = preprocess_report(text)
    assert stacktrace is not None
    assert "NullReferenceException" in stacktrace
    assert stacktrace_hash is not None
    assert len(stacktrace_hash) == 64
