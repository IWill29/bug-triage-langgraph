# State Patterns Reference

## State Design Principles

### 1. Accumulator vs. Overwrite Fields

**Accumulator fields** - grow across the agent's lifetime:
- `messages` - conversation history
- `validation_errors` - all validation attempts
- `classification_history` - all LLM classification attempts
- `risk_signals` - detected risk patterns
- `processing_warnings` - warnings/notes for human review
- `node_timings` - performance tracking

**Overwrite fields** - hold current value:
- `title` - current extracted title
- `severity` - current severity assessment
- `confidence` - latest confidence score
- `retry_count` - current retry attempt number
- `is_duplicate` - final duplicate determination
- `needs_human_review` - escalation flag

### 2. Reducer Functions

Common reducers from `operator` module:

```python
from typing import Annotated
import operator

# Append to list (most common)
errors: Annotated[list[dict], operator.add]

# Concatenate strings
log: Annotated[str, operator.add]

# Sum numbers
token_count: Annotated[int, operator.add]

# Merge dicts (last value wins per key)
metadata: Annotated[dict, lambda a, b: {**a, **b}]

# Custom reducer: max value
max_confidence: Annotated[float, max]
```

### 3. State Schema Example (Bug Triage)

```python
from typing import Annotated, TypedDict, Literal, Optional
import operator
from datetime import datetime

class BugTriageState(TypedDict):
    """Complete state schema for bug triage workflow."""
    
    # ========== INPUT (Required) ==========
    bug_report_text: str                    # Raw user input
    thread_id: str                          # Unique session ID
    
    # ========== PREPROCESSING ==========
    cleaned_report: Optional[str]           # Noise-stripped text
    extracted_stacktrace: Optional[str]     # Isolated stack trace
    stacktrace_hash: Optional[str]          # Fast dedup key
    
    # ========== RISK ASSESSMENT ==========
    risk_level: Optional[Literal["safe", "review", "escalate"]]
    risk_signals: Annotated[list[str], operator.add]  # Accumulates
    
    # ========== LLM EXTRACTION ==========
    title: Optional[str]
    severity: Optional[Literal["critical", "high", "medium", "low"]]
    components: list[str]
    reproduction_steps: Optional[str]
    confidence: float                       # 0.0-1.0
    is_feature_request: bool
    
    # ========== VALIDATION & RETRY ==========
    validation_errors: Annotated[list[dict], operator.add]
    retry_count: int                        # Current attempt
    used_premium_model: bool
    
    # ========== DUPLICATE DETECTION ==========
    duplicate_candidates: list[dict]
    is_duplicate: bool
    duplicate_issue_id: Optional[int]
    duplicate_confidence: float
    
    # ========== OUTPUT ==========
    gitea_issue_url: Optional[str]
    needs_human_review: bool
    processing_warnings: Annotated[list[str], operator.add]
    
    # ========== AUDIT TRAIL ==========
    classification_history: Annotated[list[dict], operator.add]
    node_timings: Annotated[list[dict], operator.add]
```

### 4. State Initialization

```python
def create_initial_state(bug_report: str) -> BugTriageState:
    """Initialize state with required fields."""
    import uuid
    
    return {
        "bug_report_text": bug_report,
        "thread_id": str(uuid.uuid4()),
        
        # Initialize accumulators as empty
        "risk_signals": [],
        "validation_errors": [],
        "classification_history": [],
        "node_timings": [],
        "processing_warnings": [],
        
        # Initialize scalars
        "components": [],
        "confidence": 0.0,
        "retry_count": 0,
        "is_feature_request": False,
        "used_premium_model": False,
        "is_duplicate": False,
        "duplicate_confidence": 0.0,
        "needs_human_review": False,
        
        # Optional fields start as None
        "cleaned_report": None,
        "extracted_stacktrace": None,
        "stacktrace_hash": None,
        "risk_level": None,
        "title": None,
        "severity": None,
        "reproduction_steps": None,
        "duplicate_issue_id": None,
        "gitea_issue_url": None,
    }
```

### 5. State Access Patterns

```python
def node_example(state: BugTriageState) -> dict:
    """Common patterns for accessing state."""
    
    # Safe access with .get() and defaults
    retry_count = state.get("retry_count", 0)
    errors = state.get("validation_errors", [])
    
    # Check optional fields
    if state.get("stacktrace_hash"):
        # Do stacktrace-based lookup
        pass
    
    # Access accumulators (always lists/dicts)
    last_classification = (
        state["classification_history"][-1]
        if state.get("classification_history")
        else None
    )
    
    # Build return delta
    return {
        "retry_count": retry_count + 1,
        "node_timings": [{
            "node": "node_example",
            "timestamp": datetime.now().isoformat(),
            "duration_ms": 123
        }]
    }
```

### 6. State Inspection (Debugging)

```python
# Get current state
config = {"configurable": {"thread_id": "test-123"}}
current_state = app.get_state(config)

print(f"State values: {current_state.values}")
print(f"Next node(s): {current_state.next}")
print(f"Metadata: {current_state.metadata}")

# Get state history (time-travel)
history = list(app.get_state_history(config))

for i, snapshot in enumerate(history):
    print(f"Step {i}: {snapshot.metadata.get('step')}")
    print(f"  Confidence: {snapshot.values.get('confidence')}")
    print(f"  Node: {snapshot.metadata.get('source')}")
```

### 7. State Reset (New Conversation)

```python
# Option 1: New thread ID
new_config = {"configurable": {"thread_id": str(uuid.uuid4())}}

# Option 2: Clear existing thread (destructive)
checkpointer.delete(config["configurable"]["thread_id"])

# Option 3: Update state to initial values
app.update_state(
    config,
    create_initial_state("New bug report text")
)
```

## Best Practices

1. **Keep state lean** - Everything gets serialized to DB on every node transition
2. **Use accumulators for history** - Never manually append to lists in nodes
3. **Type hints everywhere** - State schema is contract between nodes
4. **Document accumulator reducers** - Comment what operator.add does for each field
5. **Avoid nested state** - Flat is better than nested for checkpointing performance
6. **Use Optional for nullable fields** - Makes intent clear
7. **Initialize all fields** - Don't let nodes assume fields exist

## Anti-Patterns to Avoid

❌ **Mutating state in-place**
```python
def bad_node(state):
    state["errors"].append("new")  # WRONG
    return state
```

❌ **Returning modified state object**
```python
def bad_node(state):
    state["retry_count"] += 1  # WRONG
    return state
```

❌ **Not using reducers for lists**
```python
class BadState(TypedDict):
    errors: list[str]  # WRONG - will overwrite, not append
```

❌ **Deeply nested state**
```python
class BadState(TypedDict):
    triage: dict[str, dict[str, list[dict]]]  # WRONG - hard to checkpoint
```

✅ **Correct pattern**
```python
def good_node(state):
    return {
        "errors": [{"error": "new"}],  # Appends via reducer
        "retry_count": state["retry_count"] + 1
    }
```
