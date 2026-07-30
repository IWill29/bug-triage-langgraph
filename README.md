# Bug Report Triage Service

**LangGraph-based automated issue triage system**

Version: 1.0.0  
Status: Phase 1 - Infrastructure Complete

## Overview

Transforms free-text bug reports into structured, triaged issues in a self-hosted Gitea instance. Built with LangGraph for production-grade orchestration, featuring:

- **Title Generation** - Concise, descriptive titles from raw reports
- **Severity Classification** - Automatic `critical` | `high` | `medium` | `low` assignment
- **Component Labeling** - Multi-label classification (frontend, backend, api, auth, etc.)
- **Duplicate Detection** - Two-stage embedding + LLM verification
- **Graceful Degradation** - Safe defaults on unclear input
- **Production-Ready** - PostgreSQL checkpointing, structured logging, LangSmith tracing

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              LangGraph StateGraph Workflow                  │
│                                                             │
│  Preprocess → Risk Check → Fast Triage → Confidence Gate   │
│  Premium Retry ← Validate ← Duplicate Check ← Create Issue │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   PostgreSQL Checkpointer                   │
│          (Durable state, crash recovery, audit)            │
└─────────────────────────────────────────────────────────────┘
```

See [`spec.md`](spec.md) for full technical specification.

## Quick Start

### Prerequisites

- Docker Desktop or Docker Engine
- Python 3.11+ (for local development)
- OpenAI API key
- (Optional) LangSmith account for tracing

### 1. Clone and Configure

```bash
# Clone repository
git clone <repo-url>
cd langpath

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
# Required:
#   - OPENAI_API_KEY
#   - GITEA_TOKEN (generate after first startup)
# Optional:
#   - LANGSMITH_API_KEY
```

### 2. Start Services

```bash
# Start all services (Postgres, Gitea, Triage Service)
docker-compose up -d

# Watch logs
docker-compose logs -f triage-service
```

Services will be available at:
- **Gitea**: http://localhost:3000
- **Triage API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### 3. Setup Gitea

First-time setup:

1. Open http://localhost:3000
2. Complete initial setup wizard:
   - Database: PostgreSQL (pre-configured)
   - Admin account: Create username/password
   - Server domain: `localhost:3000`
   - Base URL: `http://localhost:3000/`

3. Create repository:
   - Name: `bug-reports`
   - Owner: `triagebot` (or your admin username)
   - Set as public

4. Generate API token:
   - Settings → Applications → Generate New Token
   - Scopes: `issue:read`, `issue:write`
   - Copy token to `.env` as `GITEA_TOKEN`

5. Restart triage service:
   ```bash
   docker-compose restart triage-service
   ```

### 4. Seed Test Data

Load Set A issues for duplicate detection testing:

```bash
# Enter triage service container
docker-compose exec triage-service bash

# Run seed script
python scripts/seed_gitea.py

# Verify issues created
exit
```

Check http://localhost:3000/triagebot/bug-reports/issues - you should see 4 issues (EXIST-1 through EXIST-4).

### 5. Test Triage

```bash
# Via CLI
docker-compose exec triage-service python scripts/test_triage.py "Login button not working on mobile"

# Via HTTP API
curl -X POST http://localhost:8000/api/triage \
  -H "Content-Type: application/json" \
  -d '{"report": "Login button not working on mobile Safari"}'
```

## Development

### Project Structure

```
langpath/
├── docker-compose.yml           # Infrastructure setup
├── Dockerfile                   # Triage service container
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment template
├── spec.md                      # Technical specification
│
├── src/
│   ├── main.py                  # FastAPI application
│   ├── config.py                # Configuration management
│   ├── graph/
│   │   ├── workflow.py          # LangGraph definition
│   │   ├── state.py             # State schema
│   │   └── nodes/               # Workflow nodes
│   ├── services/                # LLM, Gitea, embeddings
│   ├── models/                  # Pydantic schemas
│   └── utils/                   # Helpers, logging
│
├── tests/
│   ├── conftest.py              # Pytest fixtures
│   ├── unit/                    # Node function tests
│   ├── integration/             # End-to-end tests
│   └── fixtures/                # Sample data (Set B)
│
└── scripts/
    ├── seed_gitea.py            # Load Set A issues
    └── test_triage.py           # CLI test harness
```

### Running Tests

```bash
# All tests
docker-compose exec triage-service pytest

# Unit tests only
docker-compose exec triage-service pytest tests/unit -v

# Integration tests
docker-compose exec triage-service pytest tests/integration -v

# With coverage
docker-compose exec triage-service pytest --cov=src --cov-report=html
```

### Local Development (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Gitea via Docker
docker-compose up -d postgres gitea

# Update .env with local connection
DATABASE_URL=postgresql://triagebot:changeme@localhost:5432/langgraph
GITEA_URL=http://localhost:3000

# Run service locally
python -m src.main

# Or with hot reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `GITEA_URL` | Yes | - | Gitea base URL |
| `GITEA_TOKEN` | Yes | - | Gitea API token |
| `GITEA_REPO_OWNER` | No | `triagebot` | Repository owner username |
| `GITEA_REPO_NAME` | No | `bug-reports` | Repository name |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `LANGSMITH_API_KEY` | No | - | LangSmith tracing key |
| `LANGSMITH_PROJECT` | No | `bug-triage-dev` | LangSmith project name |
| `LANGSMITH_TRACING` | No | `true` | Enable LangSmith tracing |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `ENVIRONMENT` | No | `development` | Environment name |

## API Endpoints

### POST /api/triage

Triage a bug report.

**Request:**
```json
{
  "report": "Login button does nothing when clicked on iPhone Safari",
  "thread_id": "optional-resume-id"
}
```

**Response:**
```json
{
  "status": "created",
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "issue_url": "http://localhost:3000/triagebot/bug-reports/issues/42",
  "title": "Login button unresponsive on mobile Safari",
  "severity": "high",
  "components": ["frontend", "auth"],
  "confidence": 0.87,
  "is_duplicate": false,
  "needs_human_review": false,
  "warnings": []
}
```

### GET /health

Health check for container orchestration.

### GET /docs

OpenAPI documentation (Swagger UI).

## Next Steps (Phase 2+)

Phase 1 infrastructure is complete. Next phases:

- **Phase 2**: Core workflow nodes (preprocess, risk_check, triage)
- **Phase 3**: Duplicate detection (embeddings + LLM)
- **Phase 4**: Gitea integration
- **Phase 5**: Error handling, checkpointing
- **Phase 6**: Testing suite
- **Phase 7**: Documentation, demo prep

See [`spec.md`](spec.md) section 13 for full roadmap.

## Troubleshooting

### Gitea not accessible

```bash
# Check service status
docker-compose ps

# Check Gitea logs
docker-compose logs gitea

# Gitea takes ~60s to start first time
# Wait for: "Serving [::]:3000 with protocol http"
```

### Database connection errors

```bash
# Check PostgreSQL
docker-compose logs postgres

# Verify pgvector extension
docker-compose exec postgres psql -U triagebot -d langgraph -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

### Triage service crashes

```bash
# Check logs
docker-compose logs triage-service

# Verify environment variables
docker-compose exec triage-service env | grep -E "OPENAI|GITEA|DATABASE"

# Restart service
docker-compose restart triage-service
```

## License

MIT

## Contact

For questions or issues, see [`spec.md`](spec.md) or open an issue in Gitea.
