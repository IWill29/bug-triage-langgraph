# Bug Report Triage Service

LangGraph workflow that turns free-text bug reports into structured Gitea issues. Built for the [candidate brief](1_candidate_brief.md) — see [BRIEF_COMPLIANCE.md](BRIEF_COMPLIANCE.md) for full requirement mapping.

## Brief compliance

| Requirement | Status |
|-------------|--------|
| Title, severity, labels, repro steps from free text | ✅ |
| Duplicate check → comment/link existing issue | ✅ |
| Create issue in Gitea (or comment if duplicate) | ✅ |
| HTTP endpoint **and** CLI | ✅ |
| `docker-compose` (Gitea + Postgres + service) | ✅ |
| Seed Set A for duplicate testing | ✅ |
| README + spec with LLM steering notes | ✅ |
| Runnable demo documented below | ✅ |

**Framework:** LangGraph (explicit routing, checkpointing, testable nodes).  
**LLM:** Exercise-provided key via `OPENAI_API_KEY` in `.env`.

## Ground rules — two repos

- **Gitea** (`http://localhost:3000`) — exercise target. Commit your work here and open a PR for the onsite walkthrough (per brief).
- **GitHub** (this repo) — development history, phase branches, CI. Evaluators run the demo from this codebase via Docker; Gitea is the self-hosted issue tracker inside compose.

## Quick start (demo path)

### 1. Configure

```bash
cp .env.example .env
# Set OPENAI_API_KEY (exercise key)
# GITEA_TOKEN — after step 3 below
```

### 2. Start stack

```bash
docker compose up -d
docker compose logs -f triage-service   # wait for healthy
```

| Service | URL |
|---------|-----|
| Gitea | http://localhost:3000 |
| Triage API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

### 3. Gitea first-time setup

1. Open http://localhost:3000 — complete install wizard (Postgres is pre-wired).
2. Create repo: owner = your admin user (default `triagebot`), name = `bug-reports`, public.
3. Settings → Applications → Generate token (`issue:read`, `issue:write`).
4. Add token to `.env` as `GITEA_TOKEN`, set `GITEA_REPO_OWNER` if not `triagebot`.
5. `docker compose restart triage-service`

### 4. Seed Set A (duplicate test data)

```bash
docker compose exec triage-service python scripts/seed_gitea.py
```

Verify four issues at `http://localhost:3000/<owner>/bug-reports/issues` (EXIST-1 … EXIST-4).

### 5. Run examples

**B1 — new issue (profile upload):**

```bash
docker compose exec triage-service python scripts/test_triage.py \
  "When I upload a profile picture larger than about 5MB, the page shows a spinner forever and the picture never saves."
```

**B5 — duplicate of EXIST-1 (needs seed + token + live OpenAI):**

```bash
docker compose exec triage-service python scripts/test_triage.py \
  "I can't log in on my iPhone. I open the app in Safari, type my details, tap the login button and literally nothing happens."
```

Expected: comments on issue #1, `is_duplicate: true` — not a new issue.

**HTTP (same inputs):**

```bash
curl -s -X POST http://localhost:8000/api/triage \
  -H "Content-Type: application/json" \
  -d '{"report": "When I upload a profile picture larger than 5MB, upload spins forever."}' | jq

curl -s -X POST http://localhost:8000/api/triage \
  -H "Content-Type: application/json" \
  -d '{"report": "Login button does nothing on iPhone Safari."}' | jq
```

**CLI without Docker** (Postgres + Gitea running, deps installed):

```bash
pip install -r requirements.txt
python scripts/test_triage.py "your report here"
python -m src.main   # or: uvicorn src.main:app --reload
```

## How it works

```
Preprocess → Risk check → Triage (LLM) → Validate → Duplicate check → Gitea
                ↓ low confidence / PII
           Premium retry / human review
```

- **Duplicate detection:** Open Gitea issues → embedding similarity → LLM confirms same bug → comment instead of create.
- **Feature requests (B6):** Routed to enhancement issue, not bug.
- **Empty input (E1/E2):** API returns 422 before LLM runs.
- **Spec / decisions:** [spec.md](spec.md) (full design); [BRIEF_COMPLIANCE.md](BRIEF_COMPLIANCE.md) (brief map).

## Tests

Mocked Set B (8/8) — no live keys required:

```bash
pytest tests/ -q
# or in container:
docker compose exec triage-service pytest tests/ -q
```

Integration tests with live Gitea/OpenAI are optional; see `tests/integration/`.

## Project layout

```
src/
  main.py              # FastAPI POST /api/triage
  graph/               # LangGraph workflow + nodes
  services/            # LLM, Gitea, embeddings
scripts/
  seed_gitea.py        # Load Set A
  test_triage.py       # CLI harness
tests/
  integration/test_set_b.py   # B1–B8 mocked
docker-compose.yml
```

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Exercise LLM key |
| `GITEA_TOKEN` | Yes (live demo) | After Gitea setup |
| `GITEA_URL` | Yes | Default `http://gitea:3000` in compose |
| `GITEA_REPO_OWNER` | No | Default `triagebot` |
| `GITEA_REPO_NAME` | No | Default `bug-reports` |
| `DATABASE_URL` | Yes | Postgres for LangGraph checkpoint |
| `LANGSMITH_*` | No | Optional tracing |

## Troubleshooting

**Gitea slow first boot** — wait ~60s; check `docker compose logs gitea`.

**401 from Gitea** — regenerate token, restart triage-service.

**Duplicate check always creates new issue** — confirm Set A seeded and `GITEA_TOKEN` set.

**Tests pass but live triage fails** — `OPENAI_API_KEY` missing or invalid in `.env`.

## License

MIT
