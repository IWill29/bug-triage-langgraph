# Node Examples Reference

Complete examples of production-grade LangGraph nodes for bug triage.

## Node Template

```python
from datetime import datetime
from typing import Optional
import structlog
from src.graph.state import BugTriageState

logger = structlog.get_logger()

def template_node(state: BugTriageState) -> dict:
    """
    Node function template.
    
    Args:
        state: Current state (immutable)
    
    Returns:
        dict: Delta with changed keys only
    """
    start_time = datetime.now()
    thread_id = state.get("thread_id")
    
    # Log node start
    logger.info(
        "node_start",
        node="template_node",
        thread_id=thread_id
    )
    
    try:
        # 1. Extract inputs from state
        input_data = state["some_field"]
        
        # 2. Perform computation
        result = do_work(input_data)
        
        # 3. Calculate duration
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        # 4. Log success
        logger.info(
            "node_complete",
            node="template_node",
            thread_id=thread_id,
            duration_ms=duration_ms
        )
        
        # 5. Return delta
        return {
            "output_field": result,
            "node_timings": [{
                "node": "template_node",
                "timestamp": start_time.isoformat(),
                "duration_ms": duration_ms
            }]
        }
        
    except Exception as e:
        # Log error
        logger.error(
            "node_error",
            node="template_node",
            thread_id=thread_id,
            error=str(e),
            error_type=type(e).__name__
        )
        
        # Return error state
        return {
            "processing_warnings": [
                f"template_node failed: {type(e).__name__}"
            ]
        }
```

---

## 1. Preprocess Node

```python
import re
import hashlib
from typing import Optional

def preprocess_node(state: BugTriageState) -> dict:
    """
    Deterministic text cleaning before LLM.
    
    - Strips email signatures
    - Removes repeated whitespace
    - Extracts and hashes stack traces
    """
    text = state["bug_report_text"]
    
    # Remove common email signatures
    text = re.sub(
        r'--\s*\n.*?(?:Sent from|Best regards|Thanks).*',
        '',
        text,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Remove repeated whitespace
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Extract stack traces
    stacktrace = extract_stacktrace(text)
    stacktrace_hash = None
    
    if stacktrace:
        # Hash for fast duplicate lookup
        stacktrace_hash = hashlib.sha256(
            stacktrace.encode()
        ).hexdigest()
        
        # Replace in text (hash is enough)
        text = text.replace(stacktrace, "[STACK_TRACE_REMOVED]")
    
    return {
        "cleaned_report": text.strip(),
        "extracted_stacktrace": stacktrace,
        "stacktrace_hash": stacktrace_hash
    }


def extract_stacktrace(text: str) -> Optional[str]:
    """Extract stack trace from bug report."""
    
    # Python traceback
    python_pattern = r'Traceback \(most recent call last\):.*?(?=\n\n|\Z)'
    match = re.search(python_pattern, text, re.DOTALL)
    if match:
        return match.group(0)
    
    # JavaScript stack trace
    js_pattern = r'Error:.*?at .*?\n(?:\s+at .*?\n)+'
    match = re.search(js_pattern, text, re.DOTALL)
    if match:
        return match.group(0)
    
    return None
```

---

## 2. Risk Check Node

```python
from typing import Literal

# Keyword databases
SECURITY_KEYWORDS = [
    "sql injection", "xss", "csrf", "rce", 
    "command injection", "path traversal",
    "vulnerable", "exploit", "bypass authentication"
]

DATA_LOSS_KEYWORDS = [
    "deleted all", "lost data", "corrupted database",
    "wiped", "data gone", "records disappeared"
]

PII_PATTERNS = [
    r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
    r'\b\d{16}\b',              # Credit card
    r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b'  # Email
]


def risk_check_node(state: BugTriageState) -> dict:
    """
    Safety override for high-risk reports.
    Bypasses ML classification for security/data loss.
    """
    text = state["cleaned_report"].lower()
    signals = []
    
    # Check security patterns
    for keyword in SECURITY_KEYWORDS:
        if keyword in text:
            signals.append("security_vulnerability")
            return {
                "risk_level": "escalate",
                "risk_signals": signals,
                "severity": "critical",
                "confidence": 1.0,
                "needs_human_review": True,
                "processing_warnings": [
                    "Security vulnerability detected - bypassing ML classification"
                ]
            }
    
    # Check data loss patterns
    for keyword in DATA_LOSS_KEYWORDS:
        if keyword in text:
            signals.append("data_loss_potential")
            return {
                "risk_level": "escalate",
                "risk_signals": signals,
                "severity": "critical",
                "confidence": 1.0,
                "needs_human_review": True
            }
    
    # Check PII exposure
    import re
    for pattern in PII_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            signals.append("pii_exposure")
            return {
                "risk_level": "review",
                "risk_signals": signals,
                "needs_human_review": True
            }
    
    # Safe to proceed
    return {
        "risk_level": "safe",
        "risk_signals": []
    }


def route_risk(state: BugTriageState) -> Literal["fast_triage", "human_review"]:
    """Conditional edge based on risk level."""
    risk_level = state.get("risk_level")
    
    if risk_level in ["escalate", "review"]:
        return "human_review"
    
    return "fast_triage"
```

---

## 3. Fast Triage Node

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import ValidationError
from src.models.triage import TriageExtraction

TRIAGE_PROMPT = """You are a bug triage assistant. Extract structured information.

Rules:
- Title: concise, actionable (e.g. "Login button unresponsive on mobile Safari")
- Severity:
  * critical = data loss, security, complete system down
  * high = major feature broken, affects many users
  * medium = feature degraded, workaround exists
  * low = cosmetic, typos, minor UX
- Components: choose 1-3 most relevant
- Reproduction steps: extract if present, else null (DO NOT invent)
- Confidence: 0.0-1.0 based on report clarity
- Flag feature requests (not bugs)

Bug report:
{bug_report}"""


def fast_triage_node(state: BugTriageState) -> dict:
    """
    Initial extraction with fast/cheap model.
    Routes to premium retry if low confidence.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a bug triage assistant."),
        ("user", TRIAGE_PROMPT)
    ])
    
    try:
        # Structured output with Pydantic validation
        structured_llm = llm.with_structured_output(TriageExtraction)
        
        result = structured_llm.invoke(
            prompt.format(bug_report=state["cleaned_report"])
        )
        
        return {
            "title": result.title,
            "severity": result.severity,
            "components": result.components,
            "reproduction_steps": result.reproduction_steps,
            "confidence": result.confidence,
            "is_feature_request": result.is_feature_request,
            "used_premium_model": False,
            "classification_history": [{
                "model": "gpt-4o-mini",
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "timestamp": datetime.now().isoformat()
            }]
        }
        
    except ValidationError as e:
        # Pydantic validation failed - route to retry
        logger.warning(
            "fast_triage_validation_failed",
            thread_id=state.get("thread_id"),
            error=str(e)
        )
        
        return {
            "confidence": 0.0,
            "validation_errors": [{
                "error": str(e),
                "node": "fast_triage",
                "timestamp": datetime.now().isoformat()
            }]
        }
```

---

## 4. Premium Retry Node

```python
def premium_retry_node(state: BugTriageState) -> dict:
    """
    Retry with expensive model + error feedback.
    Used when fast model has low confidence.
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    # Build error feedback from previous attempts
    previous_errors = state.get("validation_errors", [])
    error_feedback = ""
    
    if previous_errors:
        last_error = previous_errors[-1]
        error_feedback = f"\n\nPrevious extraction failed: {last_error['error']}"
    
    # Build retry prompt with context
    retry_prompt = f"""Bug report classification (RETRY with corrections):

Report: {state["cleaned_report"]}

Previous attempt (confidence {state.get("confidence", 0.0)}):
- Title: {state.get("title", "N/A")}
- Severity: {state.get("severity", "N/A")}
- Components: {state.get("components", [])}
{error_feedback}

Re-extract with higher accuracy. Focus on:
1. More precise severity assessment
2. Complete component coverage
3. Clear reproduction steps (or explicit null if not provided)"""
    
    try:
        structured_llm = llm.with_structured_output(TriageExtraction)
        result = structured_llm.invoke(retry_prompt)
        
        return {
            "title": result.title,
            "severity": result.severity,
            "components": result.components,
            "reproduction_steps": result.reproduction_steps,
            "confidence": result.confidence,
            "retry_count": state["retry_count"] + 1,
            "used_premium_model": True,
            "classification_history": [{
                "model": "gpt-4o",
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "attempt": state["retry_count"] + 1,
                "timestamp": datetime.now().isoformat()
            }]
        }
        
    except ValidationError as e:
        return {
            "confidence": 0.0,
            "retry_count": state["retry_count"] + 1,
            "validation_errors": [{
                "error": str(e),
                "node": "premium_retry",
                "timestamp": datetime.now().isoformat()
            }]
        }
```

---

## 5. Validate Node

```python
def validate_node(state: BugTriageState) -> dict:
    """
    Schema validation + business rules.
    Applies fallback defaults after max retries.
    """
    errors = []
    
    # Title validation
    title = state.get("title", "")
    if len(title) < 10:
        errors.append("title_too_short")
    if len(title) > 100:
        errors.append("title_too_long")
    
    # Component validation
    components = state.get("components", [])
    if not components:
        errors.append("no_components_assigned")
    
    # Semantic validation
    text = state["cleaned_report"].lower()
    severity = state.get("severity")
    
    # Cosmetic bugs shouldn't be critical
    cosmetic_keywords = ["typo", "copyright year", "footer color"]
    if severity == "critical" and any(kw in text for kw in cosmetic_keywords):
        errors.append("severity_mismatch_cosmetic")
    
    # Security bugs shouldn't be low
    security_keywords = ["sql injection", "xss", "vulnerable"]
    if severity == "low" and any(kw in text for kw in security_keywords):
        errors.append("severity_mismatch_security")
    
    # If max retries reached - apply safe defaults
    if errors and state["retry_count"] >= 2:
        return {
            "severity": "medium",
            "components": components if components else ["unknown"],
            "needs_human_review": True,
            "processing_warnings": [
                f"Applied fallback defaults after {state['retry_count']} validation failures"
            ],
            "validation_errors": [{
                "errors": errors,
                "node": "validate",
                "timestamp": datetime.now().isoformat()
            }]
        }
    
    # If errors and can retry - route back
    if errors:
        return {
            "validation_errors": [{
                "errors": errors,
                "node": "validate",
                "timestamp": datetime.now().isoformat()
            }]
        }
    
    # Validation passed
    return {}
```

---

## 6. Duplicate Check Node

```python
from langchain_openai import OpenAIEmbeddings
from src.services.vector_db import find_similar_issues
from src.models.triage import DuplicateComparison

def duplicate_check_node(state: BugTriageState) -> dict:
    """
    Two-stage duplicate detection:
    1. Embedding similarity (recall)
    2. LLM semantic comparison (precision)
    """
    
    # Fast path: stacktrace hash match
    if state.get("stacktrace_hash"):
        existing = find_by_stacktrace_hash(state["stacktrace_hash"])
        if existing:
            return {
                "is_duplicate": True,
                "duplicate_issue_id": existing["id"],
                "duplicate_confidence": 1.0,
                "duplicate_candidates": [existing]
            }
    
    # Stage 1: Embedding similarity
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    query_embedding = embeddings.embed_query(state["cleaned_report"])
    
    candidates = find_similar_issues(
        query_embedding,
        k=5,
        threshold=0.72
    )
    
    if not candidates:
        return {
            "is_duplicate": False,
            "duplicate_candidates": []
        }
    
    # Stage 2: LLM semantic comparison
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    for candidate in candidates[:3]:  # Check top 3
        comparison_prompt = f"""Are these bug reports duplicates?

New report:
Title: {state["title"]}
Description: {state["cleaned_report"][:500]}

Existing issue #{candidate["id"]}:
Title: {candidate["title"]}
Description: {candidate["description"][:500]}

Duplicate means:
- Same root cause
- Same symptoms
- Fixing one would fix the other

NOT duplicates if:
- Related but different bugs
- Same component but different symptoms

Return is_duplicate (bool) and confidence (0.0-1.0)."""
        
        result = llm.with_structured_output(DuplicateComparison).invoke(
            comparison_prompt
        )
        
        # High confidence match
        if result.confidence > 0.80:
            return {
                "is_duplicate": True,
                "duplicate_issue_id": candidate["id"],
                "duplicate_confidence": result.confidence,
                "duplicate_candidates": candidates,
                "classification_history": [{
                    "action": "duplicate_detected",
                    "candidate_id": candidate["id"],
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                    "timestamp": datetime.now().isoformat()
                }]
            }
    
    # No high-confidence duplicates
    return {
        "is_duplicate": False,
        "duplicate_candidates": candidates,
        "duplicate_confidence": max(
            [c.get("similarity", 0) for c in candidates]
        )
    }
```

---

## Conditional Edge Functions

```python
from typing import Literal

def route_confidence(
    state: BugTriageState
) -> Literal["premium_retry", "validate", "fallback"]:
    """Route based on confidence score."""
    
    # Max retries exhausted
    if state["retry_count"] >= 3:
        return "fallback"
    
    # Low confidence - retry with premium
    if state["confidence"] < 0.70:
        return "premium_retry"
    
    # High confidence - validate
    return "validate"


def route_duplicate(
    state: BugTriageState
) -> Literal["create_issue", "comment_duplicate"]:
    """Route based on duplicate detection."""
    
    if state["is_duplicate"]:
        return "comment_duplicate"
    
    return "create_issue"
```
