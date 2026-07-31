# Brief Compliance Map

Maps each requirement from [`1_candidate_brief.md`](1_candidate_brief.md) to implementation artifacts. Sample data: [`2_candidate_sample_data.md`](2_candidate_sample_data.md).

## Checklist

| # | Brief requirement | Status | Where |
|---|-------------------|--------|-------|
| 1 | Free-text → title, severity, labels, repro steps (or explicit none) | ✅ | `triage.py`, `validate.py`; `TriageResponse.reproduction_steps` in `api.py` |
| 2 | Duplicate check vs open Gitea issues → comment/link, not new issue | ✅ | `duplicate.py`, `gitea.py`; live B5 verified against EXIST-1 |
| 3 | Create issue in Gitea (or comment on duplicate) | ✅ | Includes `human_review` path → `create_bug` |
| 4 | Input via HTTP endpoint **and** CLI | ✅ | `POST /api/triage` in `src/main.py`; `scripts/test_triage.py` (empty/whitespace rejected) |
| 5 | `docker-compose` with Gitea + dependencies | ✅ | `docker-compose.yml` (Postgres, Gitea, triage-service) |
| 6 | Seed Set A in Gitea for duplicate testing | ✅ | `scripts/seed_gitea.py` (EXIST-1 … EXIST-4) |
| 7 | README + short spec explaining choices and LLM steering | ✅ | `README.md` + `BRIEF_COMPLIANCE.md`; `spec.md` opens with appendix note (full detail optional) |
| 8 | Runnable demo path documented | ✅ | README Quick Start (steps 1–6) |

## Set B self-test coverage

| Sample | Expected behavior | Test |
|--------|-------------------|------|
| B1 | Structured bug, creates issue | `tests/integration/test_set_b.py::test_set_b_clean_reports_extract_and_create_issue[B1_clean]` |
| B2 | API 500, creates issue | same parametrize with `B2_api_error` |
| B3 | Vague → low confidence, human review | `test_set_b3_vague_triggers_premium_and_human_review` |
| B4 | Cosmetic urgency downgraded | `test_set_b4_cosmetic_overrides_urgent_tone` |
| B5 | Duplicate of EXIST-1 → comment on #1 | `test_set_b5_duplicate_links_existing_issue` |
| B6 | Feature request → enhancement, not bug | `test_set_b6_feature_request_routes_to_enhancement` |
| B7 | Multiple issues → warning + secondary list | `test_set_b7_multiple_issues_detected` |
| B8 | Stacktrace extracted from noisy log | `test_set_b8_noisy_log_extracts_stacktrace` |

Edge cases E1/E2 (empty / whitespace): `tests/integration/test_api_edge_cases.py` → HTTP 422; CLI rejects empty input in `scripts/test_triage.py`.

## Framework choice: LangGraph

Chose LangGraph for explicit graph routing (duplicate vs create, feature vs bug, premium retry), PostgreSQL checkpointing for crash recovery, and testable node boundaries. Plain SDK calls would work for the brief; graph structure makes failure modes visible and reviewable.

## LLM steering (what we trust / don't)

| Area | Approach |
|------|----------|
| Output shape | Pydantic structured output + validate node with retry |
| Severity inflation | Validate node downgrades cosmetic critical → low (B4) |
| Repro steps | Prompt: extract only if present; `reproduction_steps` nullable |
| Duplicates | Two-stage: embedding pre-filter + LLM confirmation (avoids false merges) |
| Vague / hostile input | `input_safety.py` + risk_check; reject empty at API (422) |
| Feature vs bug | `is_feature_request` flag routes to enhancement label |

## Ground rules: two repos

| Context | Purpose |
|---------|---------|
| **Gitea** (`localhost:3000`) | Exercise deliverable — commit work, open PR for evaluator walkthrough (per brief) |
| **GitHub** (`IWill29/bug-triage-langgraph`) | Dev workflow — phase branches, CI, SonarCloud, agent orchestration |

Both are intentional: Gitea satisfies the exercise infra requirement; GitHub is where implementation was built and reviewed.

## Manual steps (evaluator / candidate)

1. `docker compose up -d` — wait for Gitea (~60s first boot)
2. Gitea wizard → create admin, repo `bug-reports`, API token → `.env` as `GITEA_TOKEN`
3. `docker compose restart triage-service`
4. `docker compose exec triage-service python scripts/seed_gitea.py`
5. Set `OPENAI_API_KEY` from exercise-provided key in `.env`
6. Run B1/B5 via CLI or curl (see README)

## Known gaps / honest limits

- **Gitea PR (brief ground rule):** ✅ [PR #16](http://localhost:3000/triagebot/bug-reports/pulls/16) (`candidate/langpath-implementation` -> `main`; GitHub remains dev/CI).
- **Embedding search** compares against Gitea issue list in memory — sufficient for Set A size.
- **SonarCloud / phase orchestrator** — dev tooling, not required by brief.
