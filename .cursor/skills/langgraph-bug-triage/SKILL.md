---
name: langgraph-bug-triage
description: >-
  Expert guidance for building production LangGraph workflows for bug triage.
  Use when implementing or refactoring the bug report triage service, working
  with StateGraph patterns, node design, conditional routing, checkpointing,
  duplicate detection, or testing LangGraph workflows.
paths:
  - "**/graph/**/*.py"
  - "**/nodes/**/*.py"
  - "**/workflow.py"
  - "**/state.py"
---

# LangGraph Bug Triage Production Patterns

Expert guidance for building production-grade bug report triage workflows using LangGraph 0.2+, Python 3.11+, and PostgreSQL checkpointing.

## When to Use This Skill

Use this skill when:
- Implementing the bug triage LangGraph workflow from spec
- Designing StateGraph architecture or node functions
- Adding conditional routing and confidence gates
- Setting up PostgresSaver checkpointing
- Implementing duplicate detection (embedding + LLM)
- Writing tests for LangGraph workflows
- Debugging state transitions or retry loops
- Adding error handling and graceful degradation

**Related spec:** `c:\Users\Agnis\Desktop\langpath\spec.md`

---

## Core Principles (Always Apply)

### 1. Immutable State with Reducers

**Never mutate state in-place. Always return deltas.**

```python
from typing import Annotated, TypedDict
import operator

class BugTriageState(TypedDict):
    """State schema with accumulator fields."""
    
    # Overwrite fields (latest value wins)
    title: Optional[str]
    severity: Optional[Literal["critical", "high", "medium", "low"]]
    confidence: float
    retry_count: int
    
    # Accumulator fields (merge across nodes)
    validation_errors: Annotated[list[dict], operator.add]
    classification_history: Annotated[list[dict], operator.add]
    processing_warnings: Annotated[list[str], operator.add]

# ✅ CORRECT: Return delta
def validate_node(state: BugTriageState) -> dict:
    """Nodes return ONLY changed keys."""
    errors = []
    
    if not state.get("title") or len(state["title"]) < 10:
        errors.append({"error": "title_too_short", "timestamp": now()})
    
    return {
        "validation_errors": errors,  # Appends via operator.add
        "retry_count": state["retry_count"] + 1
    }

# ❌ WRONG: In-place mutation
def validate_node_wrong(state: BugTriageState) -> dict:
    state["validation_errors"].append({"error": "..."})  # BREAKS CHECKPOINTING
    state["retry_count"] += 1  # BREAKS TIME-TRAVEL
    return state
```

**Why:** Immutability enables checkpoint replay, time-travel debugging, and deterministic state snapshots.

---

### 2. Bounded Retry Loops

**Always cap retries. Include error feedback on retry.**

```python
def route_confidence(
    state: BugTriageState
) -> Literal["premium_retry", "validate", "fallback"]:
    """Route based on confidence with max retries."""
    
    # CRITICAL: Always check max retries first
    if state["retry_count"] >= 3:
        return "fallback"
    
    if state["confidence"] < 0.70:
        return "premium_retry"
    
    return "validate"

def premium_retry_node(state: BugTriageState) -> dict:
    """Retry with premium model + error feedback."""
    
    # Include previous errors in prompt
    previous_errors = state.get("validation_errors", [])
    error_feedback = ""
    if previous_errors:
        last_error = previous_errors[-1]
        error_feedback = f"\nPrevious attempt failed: {last_error['error']}"
    
    prompt = f"""Bug report classification (RETRY):

Report: {state["cleaned_report"]}

Previous confidence: {state.get("confidence", 0.0)}
{error_feedback}

Re-extract with higher accuracy."""
    
    # ... LLM call ...
    
    return {
        "retry_count": state["retry_count"] + 1,
        "classification_history": [{
            "model": "gpt-4o",
            "attempt": state["retry_count"] + 1,
            "error_feedback": error_feedback
        }]
    }
```

**Pattern:** Max 3 retries → fallback defaults → flag human review.

---

### 3. PostgresSaver (Never MemorySaver in Production)

**Use connection pools, not raw connections.**

```python
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver

# ✅ CORRECT: Connection pool for production
def setup_checkpointer() -> PostgresSaver:
    """Setup production checkpointer with connection pool."""
    pool = ConnectionPool(
        os.getenv("DATABASE_URL"),
        min_size=2,
        max_size=10,
        max_idle=300.0,  # 5 min (lower than RDS Proxy timeout)
        max_lifetime=3600.0,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            "prepare_threshold": 0,  # Disable prepared statements (PgBouncer)
        }
    )
    
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()  # Create tables
    return checkpointer

# ❌ WRONG: MemorySaver (loses state on restart)
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()  # ONLY for tests!
```

**Connection pool config:**
- `max_idle=300`: Lower than DB proxy idle timeout (RDS Proxy default: 1800s)
- `prepare_threshold=0`: Disable prepared statements for PgBouncer compatibility
- `max_size=10`: Tune based on expected concurrent executions

**Thread ID rules:**
- Keep under 255 characters (Postgres column limit)
- Use UUID for unique sessions: `str(uuid.uuid4())`
- Never reuse thread IDs across different bug reports

---

### 4. Structured Outputs with Pydantic

**Always validate LLM responses with schemas.**

```python
from pydantic import BaseModel, Field, ValidationError
from typing import Literal, Optional

class TriageExtraction(BaseModel):
    """Schema for LLM structured output."""
    
    title: str = Field(
        description="Concise bug title (5-10 words)",
        min_length=10,
        max_length=100
    )
    severity: Literal["critical", "high", "medium", "low"]
    components: list[Literal[
        "frontend", "backend", "api", "auth",
        "database", "infra", "docs", "unknown"
    ]] = Field(min_items=1)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    is_feature_request: bool = False

def fast_triage_node(state: BugTriageState) -> dict:
    """Extract with structured output."""
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    try:
        structured_llm = llm.with_structured_output(TriageExtraction)
        result = structured_llm.invoke(prompt)
        
        return {
            "title": result.title,
            "severity": result.severity,
            "components": result.components,
            "confidence": result.confidence
        }
        
    except ValidationError as e:
        # Pydantic validation failed - route to retry
        return {
            "confidence": 0.0,
            "validation_errors": [{
                "error": str(e),
                "node": "fast_triage"
            }]
        }
```

**Validation strategy:** LLM → Pydantic schema → catch ValidationError → route to premium retry.

---

### 5. Node Function Pattern

**Nodes are pure functions that transform state.**

```python
def node_template(state: BugTriageState) -> dict:
    """
    Node function signature:
    - Input: state (TypedDict)
    - Output: dict of changed keys (delta)
    - Side effects: logging, LLM calls, DB queries
    - Must be deterministic given same state
    """
    
    # 1. Extract what you need from state
    input_data = state["cleaned_report"]
    retry_count = state.get("retry_count", 0)
    
    # 2. Perform computation (LLM call, validation, etc.)
    result = do_work(input_data)
    
    # 3. Return ONLY changed keys
    return {
        "field_to_update": result,
        "retry_count": retry_count + 1,
        "node_timings": [{
            "node": "node_template",
            "duration_ms": timer.elapsed()
        }]
    }
```

**Key rules:**
- Return dict, not modified state
- Include only changed keys
- Use accumulator fields for lists/dicts
- Log at start and end of node
- Handle exceptions gracefully

---

## Bug Triage Specific Patterns

### Pattern 1: Two-Stage Duplicate Detection

**Embeddings for recall, LLM for precision.**

```python
from langchain_openai import OpenAIEmbeddings
from typing import List

def duplicate_check_node(state: BugTriageState) -> dict:
    """Two-stage duplicate detection."""
    
    # Fast check: stacktrace hash match
    if state.get("stacktrace_hash"):
        existing = find_by_stacktrace_hash(state["stacktrace_hash"])
        if existing:
            return {
                "is_duplicate": True,
                "duplicate_issue_id": existing["id"],
                "duplicate_confidence": 1.0
            }
    
    # Stage 1: Embedding similarity (recall)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    query_embedding = embeddings.embed_query(state["cleaned_report"])
    
    candidates = vector_db.similarity_search(
        query_embedding,
        k=5,
        score_threshold=0.72  # Tuned threshold
    )
    
    if not candidates:
        return {"is_duplicate": False, "duplicate_candidates": []}
    
    # Stage 2: LLM semantic comparison (precision)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    for candidate in candidates[:3]:  # Check top 3
        comparison = llm.with_structured_output(DuplicateComparison).invoke(
            f"""Are these duplicates?

New: {state["title"]} - {state["cleaned_report"]}
Existing #{candidate["id"]}: {candidate["title"]} - {candidate["description"]}

Return is_duplicate (bool) and confidence (0.0-1.0)."""
        )
        
        if comparison.confidence > 0.80:  # High confidence threshold
            return {
                "is_duplicate": True,
                "duplicate_issue_id": candidate["id"],
                "duplicate_confidence": comparison.confidence,
                "duplicate_candidates": candidates
            }
    
    return {"is_duplicate": False, "duplicate_candidates": candidates}
```

**Thresholds:**
- Embedding: 0.72 (balances precision/recall)
- LLM confidence: 0.80 (avoid false merges)
- Top-K: 5 candidates retrieved, 3 checked by LLM

**Why two stages:** Embeddings alone have high false positive rate (related ≠ duplicate).

---

### Pattern 2: Safety Override Routing

**Deterministic rules bypass ML for high-risk bugs.**

```python
def risk_check_node(state: BugTriageState) -> dict:
    """Safety override for security/data loss."""
    text = state["cleaned_report"].lower()
    signals = []
    
    # Security patterns
    security_keywords = ["sql injection", "xss", "csrf", "rce"]
    if any(kw in text for kw in security_keywords):
        return {
            "risk_level": "escalate",
            "risk_signals": ["security_vulnerability"],
            "severity": "critical",  # Override
            "confidence": 1.0,  # Bypass ML
            "needs_human_review": True
        }
    
    # Data loss patterns
    data_loss_keywords = ["deleted all", "lost data", "corrupted"]
    if any(kw in text for kw in data_loss_keywords):
        return {
            "risk_level": "escalate",
            "risk_signals": ["data_loss_potential"],
            "severity": "critical",
            "confidence": 1.0
        }
    
    # No risk detected
    return {"risk_level": "safe", "risk_signals": []}

# In graph definition
def route_risk(state: BugTriageState) -> Literal["fast_triage", "human_review"]:
    """Route based on risk level."""
    if state["risk_level"] in ["escalate", "review"]:
        return "human_review"
    return "fast_triage"

graph.add_conditional_edges(
    "risk_check",
    route_risk,
    {
        "fast_triage": "fast_triage",
        "human_review": END  # Escalate immediately
    }
)
```

**Benefits:** Critical bugs skip ML (faster, more reliable), compliance requirement.

---

### Pattern 3: Tiered LLM Strategy

**Fast model first, premium retry on low confidence.**

```python
# Config
FAST_MODEL = "gpt-4o-mini"
PREMIUM_MODEL = "gpt-4o"
CONFIDENCE_THRESHOLD = 0.70

def fast_triage_node(state: BugTriageState) -> dict:
    """Initial extraction with fast model."""
    llm = ChatOpenAI(model=FAST_MODEL, temperature=0)
    # ... extract and return ...
    return {"confidence": 0.65, "used_premium_model": False}

def premium_retry_node(state: BugTriageState) -> dict:
    """Retry with expensive model."""
    llm = ChatOpenAI(model=PREMIUM_MODEL, temperature=0)
    # ... extract with error feedback ...
    return {"confidence": 0.88, "used_premium_model": True}

def route_confidence(state: BugTriageState) -> str:
    """Route based on confidence."""
    if state["retry_count"] >= 3:
        return "fallback"
    
    if state["confidence"] < CONFIDENCE_THRESHOLD:
        return "premium_retry"
    
    return "validate"
```

**Cost analysis:**
- 90% handled by fast model (~$0.0002)
- 10% retry with premium (~$0.01)
- Average: $0.0012 per report (6x cheaper than premium-only)

---

### Pattern 4: Graceful Degradation

**Safe defaults when retries exhausted.**

```python
def validate_node(state: BugTriageState) -> dict:
    """Validate extraction with fallback."""
    errors = []
    
    # Validation checks
    if not state.get("title") or len(state["title"]) < 10:
        errors.append("title_too_short")
    
    if not state.get("components"):
        errors.append("no_components")
    
    # If validation failed after max retries - apply safe defaults
    if errors and state["retry_count"] >= 2:
        return {
            "severity": "medium",  # Safe default
            "components": state.get("components") or ["unknown"],
            "needs_human_review": True,
            "processing_warnings": [
                f"Applied fallback defaults after {state['retry_count']} retries"
            ],
            "validation_errors": [{"errors": errors}]
        }
    
    # If errors and can retry - route back
    if errors:
        return {"validation_errors": [{"errors": errors}]}
    
    # Validation passed
    return {}
```

**Fallback policy:**
- severity=medium (not critical, not low)
- components=[unknown]
- Flag needs_human_review=True
- Log warnings for monitoring

---

## Testing Patterns

### Pattern 1: Unit Tests (Node Functions)

**Test nodes in isolation without graph.**

```python
import pytest
from src.graph.state import BugTriageState
from src.graph.nodes.risk_check import risk_check_node

def test_risk_check_detects_security():
    """Security keywords trigger escalation."""
    state = BugTriageState(
        bug_report_text="Found SQL injection in login",
        cleaned_report="found sql injection in login",
        thread_id="test-1"
    )
    
    result = risk_check_node(state)
    
    assert result["risk_level"] == "escalate"
    assert "security_vulnerability" in result["risk_signals"]
    assert result["severity"] == "critical"
    assert result["confidence"] == 1.0

def test_confidence_gate_triggers_retry():
    """Low confidence routes to premium retry."""
    from src.graph.nodes.triage import route_confidence
    
    state = BugTriageState(
        confidence=0.5,
        retry_count=1
    )
    
    result = route_confidence(state)
    
    assert result == "premium_retry"

def test_max_retries_fallback():
    """After 3 retries, bypass retry loop."""
    from src.graph.nodes.triage import route_confidence
    
    state = BugTriageState(
        confidence=0.5,
        retry_count=3  # Max reached
    )
    
    result = route_confidence(state)
    
    assert result == "fallback"
```

**Run:** `pytest tests/unit -v`

---

### Pattern 2: Integration Tests (Mock LLM)

**Test graph flow with mocked external services.**

```python
import pytest
from unittest.mock import patch, AsyncMock
from langgraph.checkpoint.memory import MemorySaver
from src.graph.workflow import build_graph

@pytest.fixture
def compiled_graph():
    """Reusable graph fixture with in-memory checkpointer."""
    graph = build_graph()
    return graph.compile(checkpointer=MemorySaver())

@pytest.mark.asyncio
async def test_low_confidence_triggers_premium(compiled_graph, mocker):
    """Test confidence routing."""
    
    # Mock fast model to return low confidence
    mocker.patch(
        "src.services.llm_service.ChatOpenAI.invoke",
        return_value={
            "title": "Unclear bug",
            "confidence": 0.4
        }
    )
    
    # Mock premium model to return high confidence
    mocker.patch(
        "src.services.llm_service.ChatOpenAI.invoke",
        return_value={
            "title": "Login button unresponsive",
            "confidence": 0.9
        }
    )
    
    config = {"configurable": {"thread_id": "test-1"}}
    result = await compiled_graph.ainvoke(
        {"bug_report_text": "login broken"},
        config
    )
    
    # Verify trajectory
    history = list(compiled_graph.get_state_history(config))
    nodes_executed = [h.metadata.get("step") for h in history]
    
    assert "fast_triage" in nodes_executed
    assert "premium_retry" in nodes_executed
    assert result["used_premium_model"] is True

@pytest.mark.asyncio
async def test_duplicate_prevents_new_issue(compiled_graph, mocker):
    """Test duplicate detection flow."""
    
    # Mock embedding search
    mocker.patch(
        "src.services.embedding_service.find_similar",
        return_value=[{
            "id": 42,
            "title": "Login broken on mobile"
        }]
    )
    
    # Mock LLM to confirm duplicate
    mocker.patch(
        "src.services.llm_service.compare_duplicates",
        return_value={"is_duplicate": True, "confidence": 0.95}
    )
    
    result = await compiled_graph.ainvoke(
        {"bug_report_text": "Can't log in on iPhone"},
        {"configurable": {"thread_id": "test-dup"}}
    )
    
    assert result["is_duplicate"] is True
    assert result["duplicate_issue_id"] == 42
```

**Mocking strategy:**
- Mock where LLM is used, not where it's defined
- Use `return_value` for static responses
- Use `side_effect` for multi-turn sequences
- Always accept `**kwargs` in mocks (LangChain config injection)

**Run:** `pytest tests/integration -v -s`

---

### Pattern 3: Multi-Turn Tests (State Accumulation)

**Test state persistence across invocations.**

```python
def test_state_accumulates_across_retries(compiled_graph):
    """Verify retry attempts tracked in history."""
    config = {"configurable": {"thread_id": "test-multi"}}
    
    # Turn 1: Initial triage (low confidence)
    result1 = compiled_graph.invoke(
        {"bug_report_text": "something broken"},
        config
    )
    
    # Turn 2: Premium retry (auto-resumes)
    result2 = compiled_graph.invoke(None, config)
    
    # Verify accumulation
    assert len(result2["classification_history"]) == 2
    assert result2["retry_count"] == 1
    assert result2["classification_history"][0]["model"] == "gpt-4o-mini"
    assert result2["classification_history"][1]["model"] == "gpt-4o"

def test_interrupt_before_create_issue(compiled_graph):
    """Test human-in-the-loop approval gate."""
    from langgraph.checkpoint.memory import MemorySaver
    
    graph = build_graph()
    app = graph.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["create_issue"]
    )
    
    config = {"configurable": {"thread_id": "test-hitl"}}
    
    # Run until interrupt
    result = app.invoke(
        {"bug_report_text": "test bug"},
        config
    )
    
    # Check state is waiting
    state = app.get_state(config)
    assert state.next == ("create_issue",)
    
    # Resume after approval
    final = app.invoke(None, config)
    assert "gitea_issue_url" in final
```

---

## Error Handling & Observability

### Error Handler Pattern

```python
from langgraph.types import TimeoutPolicy, RetryPolicy

def handle_triage_error(error: Exception, state: BugTriageState) -> dict:
    """Graceful degradation on triage failure."""
    logger.error(
        "triage_node_failed",
        error=str(error),
        error_type=type(error).__name__,
        retry_count=state.get("retry_count", 0),
        thread_id=state.get("thread_id")
    )
    
    return {
        "severity": "medium",
        "components": ["unknown"],
        "confidence": 0.0,
        "needs_human_review": True,
        "processing_warnings": [f"Triage failed: {type(error).__name__}"]
    }

# In graph definition
graph.add_node(
    "fast_triage",
    fast_triage_node,
    timeout_policy=TimeoutPolicy(timeout=30.0),
    retry_policy=RetryPolicy(
        retry_on=ValidationError,
        max_attempts=3,
        initial_interval=0.5,
        backoff_factor=2.0
    ),
    error_handler=handle_triage_error
)
```

**Timeout values:**
- Preprocessing: 15s
- LLM nodes: 30s
- External APIs: 45s

---

### Structured Logging Pattern

```python
import structlog
from datetime import datetime

logger = structlog.get_logger()

def fast_triage_node(state: BugTriageState) -> dict:
    start_time = datetime.now()
    
    logger.info(
        "node_start",
        node="fast_triage",
        thread_id=state.get("thread_id"),
        retry_count=state.get("retry_count", 0),
        report_length=len(state["cleaned_report"])
    )
    
    # ... node logic ...
    
    duration_ms = (datetime.now() - start_time).total_seconds() * 1000
    
    logger.info(
        "node_complete",
        node="fast_triage",
        thread_id=state.get("thread_id"),
        confidence=result["confidence"],
        severity=result["severity"],
        duration_ms=duration_ms
    )
    
    return result
```

**Always log:**
- thread_id (trace across nodes)
- node name
- duration_ms
- error type if failed
- retry_count

---

> **Note:** LangSmith tracing was removed from this project. Use **structlog only** for observability.

---

## Common Pitfalls (Avoid These)

### ❌ Pitfall 1: In-Place State Mutation

```python
# WRONG
def node(state: BugTriageState) -> dict:
    state["errors"].append("new_error")  # Breaks checkpointing
    return state

# CORRECT
def node(state: BugTriageState) -> dict:
    return {
        "errors": [{"error": "new_error"}]  # Appends via reducer
    }
```

---

### ❌ Pitfall 2: Mixing Static Edges and Command

```python
# WRONG: Can't mix add_edge and Command()
graph.add_edge("node_a", "node_b")  # Static
# Then in node_a:
return Command(goto="node_c")  # Conflict!

# CORRECT: Use one pattern consistently
graph.add_conditional_edges("node_a", router_fn)
```

---

### ❌ Pitfall 3: Unbounded Recursion

```python
# WRONG: No retry cap
def route(state):
    if state["confidence"] < 0.7:
        return "retry"  # Infinite loop possible!
    return "validate"

# CORRECT: Always check max attempts
def route(state):
    if state["retry_count"] >= 3:
        return "fallback"
    if state["confidence"] < 0.7:
        return "retry"
    return "validate"
```

---

### ❌ Pitfall 4: Raw Connection (Not Pool)

```python
# WRONG: Holds connection for entire run
import psycopg
conn = psycopg.connect(db_uri)
checkpointer = PostgresSaver(conn)  # Connection timeout risk

# CORRECT: Use connection pool
from psycopg_pool import ConnectionPool
pool = ConnectionPool(db_uri, max_size=10)
checkpointer = PostgresSaver(pool)
```

---

### ❌ Pitfall 5: No Error Feedback on Retry

```python
# WRONG: Retry without context
def retry_node(state):
    return llm.invoke(prompt)  # Why did previous attempt fail?

# CORRECT: Include error feedback
def retry_node(state):
    errors = state.get("validation_errors", [])
    feedback = f"Previous errors: {errors[-1]}" if errors else ""
    prompt = f"{base_prompt}\n{feedback}"
    return llm.invoke(prompt)
```

---

## Quick Reference

### Graph Setup Template

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from typing import Literal

# 1. Define state
class BugTriageState(TypedDict):
    # ... fields ...

# 2. Build graph
graph = StateGraph(BugTriageState)

# 3. Add nodes
graph.add_node("preprocess", preprocess_node)
graph.add_node("risk_check", risk_check_node)
graph.add_node("fast_triage", fast_triage_node)
graph.add_node("premium_retry", premium_retry_node)
graph.add_node("validate", validate_node)
graph.add_node("duplicate_check", duplicate_check_node)
graph.add_node("create_issue", create_issue_node)

# 4. Set entry point
graph.set_entry_point("preprocess")

# 5. Add edges
graph.add_edge("preprocess", "risk_check")

# 6. Add conditional routing
def route_risk(state) -> Literal["fast_triage", "human_review"]:
    return "human_review" if state["risk_level"] == "escalate" else "fast_triage"

graph.add_conditional_edges(
    "risk_check",
    route_risk,
    {"fast_triage": "fast_triage", "human_review": END}
)

# 7. Compile with checkpointer
checkpointer = setup_checkpointer()
app = graph.compile(
    checkpointer=checkpointer,
    recursion_limit=50
)
```

---

## Additional Resources

### Official Documentation
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [Pydantic Validation](https://docs.pydantic.dev/latest/)

### Production Patterns
- [LangGraph in Production](https://www.kalviumlabs.ai/blog/langgraph-in-production-stateful-multi-step-agents/)
- [Design Patterns Repository](https://github.com/SaqlainXoas/langgraph-design-patterns)

### Project Spec
- **Spec:** `c:\Users\Agnis\Desktop\langpath\spec.md`
- **State schema:** See section "State Management"
- **Node specs:** See section "Node Specifications"
- **Testing strategy:** See section "Testing Strategy"

---

## Troubleshooting

### Connection Timeout Issues
- Use `ConnectionPool` not raw `Connection`
- Set `max_idle` lower than DB proxy timeout
- Set `prepare_threshold=0` for PgBouncer

### State Not Persisting
- Verify checkpointer is PostgresSaver (not MemorySaver)
- Check thread_id is consistent across invocations
- Ensure nodes return dicts, not modified state

### LLM Mocking Fails in Tests
- Mock where LLM is imported/used, not where defined
- Accept `**kwargs` in mock functions
- Use `side_effect` for multi-turn sequences

### Duplicate Detection Inaccurate
- Tune embedding threshold (try 0.68-0.75 range)
- Increase LLM confidence threshold (0.85+)
- Add stacktrace hash fast-path

---

**Remember:** Read this skill fully before implementing workflow nodes or adding conditional routing. The patterns here are battle-tested and align with the spec.
