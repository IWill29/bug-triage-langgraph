# Testing Patterns Reference

## Testing Pyramid for LangGraph

```
        /\
       /  \      E2E Tests (Real LLM, Real DB)
      /----\     - Smoke tests
     /      \    - Weekly regression
    /--------\   
   /  Integ   \  Integration Tests (Mock LLM, Real Graph)
  /------------\ - Full graph flows
 /    Unit      \ - Conditional routing
/----------------\ - State transitions
   
Unit Tests (No Graph)
- Node functions
- Pure logic
- Validators
```

## Layer 1: Unit Tests (Fast, Isolated)

### Node Function Tests

```python
# tests/unit/test_nodes.py
import pytest
from src.graph.state import BugTriageState
from src.graph.nodes.risk_check import risk_check_node

class TestRiskCheckNode:
    """Test risk check node in isolation."""
    
    def test_security_keyword_triggers_escalation(self):
        """Security patterns bypass ML."""
        state = BugTriageState(
            bug_report_text="test",
            cleaned_report="found sql injection in login form"
        )
        
        result = risk_check_node(state)
        
        assert result["risk_level"] == "escalate"
        assert "security_vulnerability" in result["risk_signals"]
        assert result["severity"] == "critical"
        assert result["confidence"] == 1.0
    
    def test_data_loss_triggers_escalation(self):
        """Data loss patterns bypass ML."""
        state = BugTriageState(
            cleaned_report="deleted all user records"
        )
        
        result = risk_check_node(state)
        
        assert result["risk_level"] == "escalate"
        assert "data_loss_potential" in result["risk_signals"]
    
    def test_safe_report_passes_through(self):
        """Normal bugs proceed to triage."""
        state = BugTriageState(
            cleaned_report="button not working on mobile"
        )
        
        result = risk_check_node(state)
        
        assert result["risk_level"] == "safe"
        assert result["risk_signals"] == []


class TestConfidenceRouting:
    """Test conditional routing logic."""
    
    def test_low_confidence_triggers_retry(self):
        from src.graph.nodes.triage import route_confidence
        
        state = BugTriageState(
            confidence=0.5,
            retry_count=1
        )
        
        assert route_confidence(state) == "premium_retry"
    
    def test_high_confidence_proceeds_to_validate(self):
        from src.graph.nodes.triage import route_confidence
        
        state = BugTriageState(
            confidence=0.85,
            retry_count=0
        )
        
        assert route_confidence(state) == "validate"
    
    def test_max_retries_bypass_loop(self):
        from src.graph.nodes.triage import route_confidence
        
        state = BugTriageState(
            confidence=0.3,  # Still low
            retry_count=3    # Max reached
        )
        
        # Should skip retry even with low confidence
        assert route_confidence(state) == "fallback"


class TestValidationNode:
    """Test validation logic."""
    
    def test_title_too_short_fails_validation(self):
        from src.graph.nodes.validate import validate_node
        
        state = BugTriageState(
            title="Bug",  # Too short
            components=["frontend"],
            retry_count=0
        )
        
        result = validate_node(state)
        
        assert "validation_errors" in result
        errors = result["validation_errors"]
        assert any("title_too_short" in str(e) for e in errors)
    
    def test_max_retries_applies_fallback_defaults(self):
        from src.graph.nodes.validate import validate_node
        
        state = BugTriageState(
            title="x",  # Invalid
            components=[],  # Invalid
            retry_count=2  # Max retries
        )
        
        result = validate_node(state)
        
        assert result["severity"] == "medium"
        assert "unknown" in result["components"]
        assert result["needs_human_review"] is True
```

**Run:** `pytest tests/unit -v --cov=src/graph/nodes`

---

## Layer 2: Integration Tests (Graph Flow)

### Mock LLM Pattern

```python
# tests/integration/test_workflow.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage
from src.graph.workflow import build_graph

@pytest.fixture
def compiled_graph():
    """Graph fixture with in-memory checkpointer."""
    graph = build_graph()
    return graph.compile(checkpointer=MemorySaver())


class TestConfidenceRetryFlow:
    """Test low confidence triggers premium retry."""
    
    @pytest.mark.asyncio
    async def test_low_confidence_retry_path(self, compiled_graph):
        """Test full retry flow."""
        
        # Track which models were called
        call_tracker = {"fast": 0, "premium": 0}
        
        def mock_fast_invoke(*args, **kwargs):
            call_tracker["fast"] += 1
            return AIMessage(content='{"title": "Bug", "confidence": 0.4}')
        
        def mock_premium_invoke(*args, **kwargs):
            call_tracker["premium"] += 1
            return AIMessage(content='{"title": "Login broken", "confidence": 0.9}')
        
        with patch("src.services.llm_service.ChatOpenAI") as mock_llm:
            # Configure model factory
            mock_llm.return_value.with_structured_output.return_value.invoke.side_effect = [
                mock_fast_invoke,
                mock_premium_invoke
            ]
            
            config = {"configurable": {"thread_id": "test-retry"}}
            result = await compiled_graph.ainvoke(
                {"bug_report_text": "login thing not working"},
                config
            )
            
            # Verify both models were called
            assert call_tracker["fast"] == 1
            assert call_tracker["premium"] == 1
            
            # Verify final state
            assert result["used_premium_model"] is True
            assert result["confidence"] > 0.7
            assert result["retry_count"] == 1
            
            # Verify node execution order
            history = list(compiled_graph.get_state_history(config))
            nodes = [h.metadata.get("source") for h in history if h.metadata.get("source")]
            
            assert "fast_triage" in nodes
            assert "premium_retry" in nodes


class TestDuplicateDetection:
    """Test duplicate detection flow."""
    
    @pytest.mark.asyncio
    async def test_duplicate_prevents_new_issue(self, compiled_graph, mocker):
        """Duplicates route to comment, not create."""
        
        # Mock embedding service
        mock_embeddings = mocker.patch("src.services.embedding_service.find_similar")
        mock_embeddings.return_value = [{
            "id": 42,
            "title": "Login broken on mobile Safari",
            "description": "Button does nothing when tapped",
            "score": 0.85
        }]
        
        # Mock LLM comparison
        mock_compare = mocker.patch("src.services.llm_service.compare_duplicates")
        mock_compare.return_value = {
            "is_duplicate": True,
            "confidence": 0.93,
            "reasoning": "Same issue, same browser"
        }
        
        config = {"configurable": {"thread_id": "test-dup"}}
        result = await compiled_graph.ainvoke(
            {"bug_report_text": "Can't log in on iPhone Safari"},
            config
        )
        
        # Verify duplicate detection
        assert result["is_duplicate"] is True
        assert result["duplicate_issue_id"] == 42
        assert "/issues/42" in result["gitea_issue_url"]
        
        # Verify create_issue node was NOT called
        history = list(compiled_graph.get_state_history(config))
        nodes = [h.metadata.get("source") for h in history]
        assert "create_issue" not in nodes
        assert "comment_duplicate" in nodes


class TestSecurityBypass:
    """Test security reports bypass ML triage."""
    
    @pytest.mark.asyncio
    async def test_security_keyword_skips_llm(self, compiled_graph, mocker):
        """Security bugs escalate immediately."""
        
        # Mock LLM to verify it's NOT called
        mock_llm = mocker.patch("src.services.llm_service.ChatOpenAI")
        
        config = {"configurable": {"thread_id": "test-sec"}}
        result = await compiled_graph.ainvoke(
            {"bug_report_text": "Found SQL injection in /api/users"},
            config
        )
        
        # Verify LLM was never invoked
        assert mock_llm.call_count == 0
        
        # Verify overrides applied
        assert result["severity"] == "critical"
        assert result["confidence"] == 1.0
        assert "security_vulnerability" in result["risk_signals"]
        assert result["needs_human_review"] is True
        
        # Verify fast_triage was skipped
        history = list(compiled_graph.get_state_history(config))
        nodes = [h.metadata.get("source") for h in history]
        assert "risk_check" in nodes
        assert "fast_triage" not in nodes
```

**Run:** `pytest tests/integration -v -s`

---

## Layer 3: Multi-Turn Tests (State Persistence)

```python
class TestStatePersistence:
    """Test state accumulation across invocations."""
    
    def test_classification_history_accumulates(self, compiled_graph):
        """History grows with each attempt."""
        config = {"configurable": {"thread_id": "test-history"}}
        
        # First classification
        result1 = compiled_graph.invoke(
            {"bug_report_text": "vague bug report"},
            config
        )
        
        assert len(result1["classification_history"]) == 1
        
        # Second classification (auto-resume if low confidence)
        result2 = compiled_graph.invoke(None, config)
        
        # History should accumulate
        assert len(result2["classification_history"]) == 2
        assert result2["classification_history"][0]["model"] == "gpt-4o-mini"
        assert result2["classification_history"][1]["model"] == "gpt-4o"
    
    def test_node_timings_accumulate(self, compiled_graph):
        """Timings tracked for all nodes."""
        config = {"configurable": {"thread_id": "test-timings"}}
        
        result = compiled_graph.invoke(
            {"bug_report_text": "test bug"},
            config
        )
        
        timings = result["node_timings"]
        assert len(timings) > 0
        
        # Verify structure
        assert all("node" in t for t in timings)
        assert all("duration_ms" in t for t in timings)
        
        # Verify expected nodes
        node_names = [t["node"] for t in timings]
        assert "preprocess" in node_names
        assert "risk_check" in node_names


class TestHumanInTheLoop:
    """Test interrupt/resume patterns."""
    
    def test_interrupt_before_create_issue(self):
        """Pause for approval before creating issue."""
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
        
        # Check state is paused
        state = app.get_state(config)
        assert state.next == ("create_issue",)
        
        # Verify data is ready
        assert result.get("title")
        assert result.get("severity")
        assert result.get("is_duplicate") is not None
        
        # Resume after approval
        final = app.invoke(None, config)
        assert "gitea_issue_url" in final
    
    def test_update_state_before_resume(self):
        """Human can modify state before resuming."""
        graph = build_graph()
        app = graph.compile(
            checkpointer=MemorySaver(),
            interrupt_before=["create_issue"]
        )
        
        config = {"configurable": {"thread_id": "test-modify"}}
        
        # Run until interrupt
        app.invoke({"bug_report_text": "test"}, config)
        
        # Human modifies severity
        app.update_state(
            config,
            {"severity": "high", "components": ["frontend", "auth"]}
        )
        
        # Resume with modified state
        final = app.invoke(None, config)
        assert final["severity"] == "high"
        assert "frontend" in final["components"]
```

---

## Mock Patterns

### Pattern 1: Simple Return Value

```python
@patch("src.services.llm_service.ChatOpenAI.invoke")
def test_simple_mock(mock_invoke):
    """Single static response."""
    mock_invoke.return_value = AIMessage(
        content='{"title": "Test", "confidence": 0.8}'
    )
    
    # ... test code ...
```

### Pattern 2: Side Effect (Sequence)

```python
@patch("src.services.llm_service.ChatOpenAI.invoke")
def test_sequence_mock(mock_invoke):
    """Different responses per call."""
    mock_invoke.side_effect = [
        AIMessage(content='{"confidence": 0.4}'),  # First call
        AIMessage(content='{"confidence": 0.9}'),  # Second call
    ]
    
    # ... test code ...
```

### Pattern 3: Conditional Mock

```python
@patch("src.services.llm_service.ChatOpenAI")
def test_conditional_mock(mock_llm_class):
    """Different responses based on model."""
    
    def mock_factory(model, **kwargs):
        mock = MagicMock()
        if model == "gpt-4o-mini":
            mock.invoke.return_value = AIMessage(content='{"confidence": 0.4}')
        else:  # gpt-4o
            mock.invoke.return_value = AIMessage(content='{"confidence": 0.9}')
        return mock
    
    mock_llm_class.side_effect = mock_factory
    
    # ... test code ...
```

### Pattern 4: Async Mock

```python
@pytest.mark.asyncio
@patch("src.services.llm_service.ChatOpenAI.ainvoke", new_callable=AsyncMock)
async def test_async_mock(mock_ainvoke):
    """Async LLM calls."""
    mock_ainvoke.return_value = AIMessage(content="test")
    
    result = await graph.ainvoke(...)
```

---

## Test Fixtures

```python
# tests/conftest.py
import pytest
from langgraph.checkpoint.memory import MemorySaver
from src.graph.workflow import build_graph

@pytest.fixture
def memory_checkpointer():
    """In-memory checkpointer for tests."""
    return MemorySaver()

@pytest.fixture
def compiled_graph(memory_checkpointer):
    """Compiled graph with test checkpointer."""
    graph = build_graph()
    return graph.compile(checkpointer=memory_checkpointer)

@pytest.fixture
def test_config():
    """Test configuration with unique thread ID."""
    import uuid
    return {"configurable": {"thread_id": f"test-{uuid.uuid4()}"}}

@pytest.fixture
def sample_bug_reports():
    """Test data fixtures."""
    return {
        "clear": "Login button doesn't work on mobile Safari iOS 17",
        "vague": "the thing is broken",
        "security": "Found SQL injection in /api/users endpoint",
        "duplicate": "Can't log in on iPhone Safari browser"
    }
```

---

## Coverage Goals

- **Unit tests:** 90%+ coverage on node functions
- **Integration tests:** All conditional paths tested
- **Multi-turn tests:** State accumulation verified

**Run with coverage:**
```bash
pytest tests/ -v --cov=src --cov-report=html
```

**View report:**
```bash
open htmlcov/index.html
```
