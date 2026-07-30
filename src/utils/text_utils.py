"""
Text preprocessing utilities
Deterministic cleaning before LLM processing
"""

import re
import hashlib
from typing import Optional, Tuple


def strip_email_signatures(text: str) -> str:
    """
    Remove common email signature patterns
    
    Args:
        text: Input text
        
    Returns:
        Text with signatures removed
    """
    # Remove "Sent from", "Best regards", etc.
    patterns = [
        r'Sent from my .*',
        r'Best regards,.*',
        r'Kind regards,.*',
        r'Thanks,.*',
        r'Cheers,.*',
    ]
    
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
    
    return text


def remove_repeated_whitespace(text: str) -> str:
    """
    Collapse multiple whitespace characters
    
    Args:
        text: Input text
        
    Returns:
        Text with normalized whitespace
    """
    # Replace multiple newlines with double newline
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Replace multiple spaces with single space
    text = re.sub(r' {2,}', ' ', text)
    
    return text.strip()


def extract_stacktrace(text: str) -> Optional[str]:
    """
    Extract stack trace from bug report
    
    Args:
        text: Input text
        
    Returns:
        Extracted stack trace or None
    """
    # Pattern for common stack trace formats
    # Python: "Traceback (most recent call last):"
    # Java: "Exception in thread"
    # JavaScript: "Error: ... at"
    
    patterns = [
        r'Traceback \(most recent call last\):.*?(?=\n\n|\Z)',
        r'Exception in thread.*?(?=\n\n|\Z)',
        r'Error:.*?at .*?(?=\n\n|\Z)',
        r'\[ERROR\].*?(?=\n\n|\Z)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
        if match:
            return match.group(0)
    
    return None


def hash_stacktrace(stacktrace: str) -> str:
    """
    Generate hash of stack trace for fast duplicate detection
    
    Args:
        stacktrace: Stack trace text
        
    Returns:
        SHA256 hash hex string
    """
    return hashlib.sha256(stacktrace.encode()).hexdigest()


def preprocess_report(text: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Full preprocessing pipeline
    
    Args:
        text: Raw bug report text
        
    Returns:
        Tuple of (cleaned_text, stacktrace, stacktrace_hash)
    """
    # Remove email noise
    text = strip_email_signatures(text)
    
    # Extract stack trace
    stacktrace = extract_stacktrace(text)
    stacktrace_hash = hash_stacktrace(stacktrace) if stacktrace else None
    
    # Remove stack trace from main text (hash is enough)
    if stacktrace:
        text = text.replace(stacktrace, "[STACK_TRACE_REMOVED]")
    
    # Normalize whitespace
    text = remove_repeated_whitespace(text)
    
    return text, stacktrace, stacktrace_hash


def detect_pii(text: str) -> bool:
    """
    Detect potential PII in text
    
    Args:
        text: Input text
        
    Returns:
        True if PII patterns detected
    """
    # Email pattern
    if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
        return True
    
    # Credit card pattern (basic)
    if re.search(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', text):
        return True
    
    # SSN pattern
    if re.search(r'\b\d{3}-\d{2}-\d{4}\b', text):
        return True
    
    return False
