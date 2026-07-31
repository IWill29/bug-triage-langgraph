# LangGraph Bug Triage Skill

Production-grade patterns for building bug report triage workflows with LangGraph 0.2+, Python 3.11+, and PostgreSQL checkpointing.

## Skill Contents

### Core Skill
- **[SKILL.md](./SKILL.md)** - Main skill file with all patterns and best practices

### Reference Guides
- **[state-patterns.md](./references/state-patterns.md)** - State schema design, reducers, accumulators
- **[node-examples.md](./references/node-examples.md)** - Complete node implementations
- **[testing-patterns.md](./references/testing-patterns.md)** - Unit, integration, and multi-turn tests

## When to Use

Use this skill when:
- Implementing the bug triage workflow from `spec.md`
- Designing StateGraph architecture
- Setting up PostgresSaver checkpointing
- Writing tests for LangGraph workflows
- Debugging state transitions or retry loops

## Quick Start

1. **Read the main skill first**: [SKILL.md](./SKILL.md)
2. **Check state patterns**: [state-patterns.md](./references/state-patterns.md)
3. **Copy node templates**: [node-examples.md](./references/node-examples.md)
4. **Write tests**: [testing-patterns.md](./references/testing-patterns.md)

## Core Principles

1. **Immutable state** - Never mutate, always return deltas
2. **Bounded retries** - Max 3 attempts with error feedback
3. **PostgresSaver** - Connection pools, not raw connections
4. **Structured outputs** - Pydantic validation on all LLM responses
5. **Two-stage duplicates** - Embeddings for recall, LLM for precision

## Project Context

**Related files:**
- `c:\Users\Agnis\Desktop\langpath\spec.md` - Complete technical specification
- `src/graph/state.py` - State schema definition
- `src/graph/workflow.py` - Graph assembly
- `src/graph/nodes/` - Node implementations

## Common Patterns

### State Schema
```python
class BugTriageState(TypedDict):
    # Overwrite fields
    title: Optional[str]
    confidence: float
    
    # Accumulator fields
    validation_errors: Annotated[list[dict], operator.add]
```

### Node Function
```python
def node(state: BugTriageState) -> dict:
    """Return delta, not modified state."""
    return {
        "field": new_value,
        "retry_count": state["retry_count"] + 1
    }
```

### Checkpointer Setup
```python
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

pool = ConnectionPool(db_uri, max_size=10, max_idle=300.0)
checkpointer = PostgresSaver(pool)
```

### Testing
```python
from langgraph.checkpoint.memory import MemorySaver

@pytest.fixture
def compiled_graph():
    graph = build_graph()
    return graph.compile(checkpointer=MemorySaver())
```

## Additional Resources

- [LangGraph Official Docs](https://langchain-ai.github.io/langgraph/)
- [LangGraph Design Patterns](https://github.com/SaqlainXoas/langgraph-design-patterns)
- [Production Patterns Article](https://www.kalviumlabs.ai/blog/langgraph-in-production-stateful-multi-step-agents/)
