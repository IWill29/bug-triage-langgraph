# Implementation Workflow

You drive the project with **one command**. The [phase-orchestrator](.cursor/agents/phase-orchestrator/agent.md) runs the full agent chain automatically — no manual `@agent` picks at each step.

## What You Say

| Command | What happens |
|---------|--------------|
| **`start phase 2`** | Full pipeline for Phase 2: branch → implement → audit → QA → fix loops → PR → **PR checks** |
| **`next`** / **`continue`** | Same pipeline for the next unchecked phase (currently Phase 2) |
| **`merge`** / **`merge pr`** | Squash-merge the open phase PR (only when you approve) |
| **`status`** | Phase checklist, open PRs, last audit/QA summary, **latest PR check results** |
| **`check pr`** / **`check pr 4`** | Re-run [pr-checker](.cursor/agents/pr-checker/agent.md) on open PR (or PR #4) — CI, SonarCloud, merge readiness |

Example session:

```
You:  next
Agent: [creates phase-2-workflow-nodes, implements, audits, tests, opens PR]
Agent: [polls CI + SonarCloud via pr-checker]
Agent: PR #4 — ✅ Ready (8/8 QA, auditor pass, all checks green). Say "merge" when ready.

You:  merge
Agent: [squash-merges PR, updates checklist]
```

Re-check CI anytime:

```
You:  check pr 4
Agent: [PR Check Report — status, GitHub checks table, SonarCloud gate, merge recommendation]
```

## What Runs Automatically

```
You: "start phase N" / "next"
         │
         ▼
   phase-orchestrator
         │
         ├─ 1. Branch from main     phase-{N}-{description}
         ├─ 2. Implement            generalPurpose + langgraph-bug-triage skill
         ├─ 3. @spec-architect      only if spec.md changed
         ├─ 4. @code-auditor        always — spec compliance
         │      └─ critical? → @bug-fixer → re-audit (max 2 loops)
         ├─ 5. @qa-tester           always before PR
         │      Phase 1: env only | Phase 2+: full Set B + edge cases
         │      └─ fail? → @bug-fixer → re-test (max 3 loops)
         ├─ 6. Push branch
         ├─ 7. gh pr create         template with audit + QA results
         ├─ 8. @pr-checker          poll CI (max 10 min), SonarCloud gate, merge readiness
         │      └─ CI fail? → @bug-fixer → re-check (max 2 loops)
         └─ 9. Report PR URL + check summary   does NOT merge unless you say "merge"
```

## PR Verification (automatic)

After every PR is opened, the orchestrator **always** runs `@pr-checker`. You do not need to open GitHub Actions or SonarCloud manually.

The checker verifies:

- **GitHub checks** — all PR status checks via `gh pr checks` and `statusCheckRollup`
- **SonarCloud GitHub App** — check name **`SonarCloud Code Analysis`** (App-only; no `sonarqube.yml` workflow)
- **SonarCloud MCP** — `get_project_quality_gate_status` when authenticated (secondary confirmation)
- **Merge readiness** — conflicts, pending required checks, overall ✅ / ⚠️ / ❌ status

**SonarCloud on docs-only PRs:** PRs that only change `.cursor/`, `*.md`, or other non-code paths typically do **not** trigger the SonarCloud App. pr-checker reports this as **SKIPPED (no analyzable code in diff)** — not a failure. Code PRs (`src/`, `tests/`, `*.py`) should show the App check; if missing, pr-checker reports **MISSING** and warns to verify App installation.

**Never auto-merges** — even when all checks pass. You still say **`merge`** when ready.

## Agent Roles

| Agent | When | Job |
|-------|------|-----|
| **phase-orchestrator** | You say start/next/continue | Runs entire pipeline, delegates everything |
| **generalPurpose** | Every phase step 2 | Implements code from spec + langgraph-bug-triage skill |
| **spec-architect** | spec.md changed | Validates architecture before merge |
| **code-auditor** | Every phase step 4 | Audits code vs `spec.md` — **mandatory** |
| **qa-tester** | Every phase step 5 | Phase 1: Docker/Gitea/DB/LLM; Phase 2+: Set B — **mandatory** |
| **bug-fixer** | Audit, QA, or CI failures | Fixes issues, triggers re-audit, re-test, or re-check |
| **pr-checker** | After every PR create; `check pr` | Polls GitHub checks, SonarCloud gate, merge readiness — **mandatory** |

### pr-checker responsibilities

| Responsibility | Details |
|----------------|---------|
| Poll GitHub checks | `gh pr checks N --watch --interval 30` — max 10 min, then report pending |
| SonarCloud App check | Look for **`SonarCloud Code Analysis`** in `statusCheckRollup` — primary source of truth |
| SonarCloud MCP gate | `get_project_quality_gate_status` via MCP when authed; else MCP SKIPPED |
| Docs-only PRs | SonarCloud NOT RUN expected — report SKIPPED, not blocked |
| Code PRs without Sonar | Report MISSING — verify SonarCloud GitHub App is installed |
| Merge readiness | Conflicts, `mergeStateStatus`, required checks pending |
| Report format | ✅ Ready / ⚠️ Warnings / ❌ Blocked + checks table + SonarCloud section |
| CI fix loop | Failed code/test/SonarCloud checks → `@bug-fixer` → push → re-check (max 2 loops) |
| No auto-merge | Reports "merge: yes/no" — user must say `merge` |

You never invoke these directly during normal phase work — the orchestrator does. Use **`check pr`** anytime to refresh PR status.

## Phase Status

- [x] **Phase 0:** Architecture (on `main`)
- [x] **Phase 1:** Infrastructure (merged [PR #2](https://github.com/IWill29/bug-triage-langgraph/pull/2))
- [ ] **Phase 2:** Workflow nodes — **NEXT** (`phase-2-workflow-nodes`)
- [ ] **Phase 3:** Production hardening (`phase-3-production-hardening`)
- [ ] **Phase 4:** Testing (`phase-4-testing`)

After Phase 1 merge, say **`next`** to start Phase 2.

## Phase Scope (quick reference)

| Phase | Branch | Focus |
|-------|--------|-------|
| 2 | `phase-2-workflow-nodes` | 10 LangGraph nodes, routing, checkpointing |
| 3 | `phase-3-production-hardening` | Observability, rate limits, hostile input |
| 4 | `phase-4-testing` | Unit/integration tests, full Set B validation |

Details: [`spec.md`](spec.md), [`.cursor/rules/implementation-workflow.mdc`](.cursor/rules/implementation-workflow.mdc).

## Rules

- One phase = one feature branch + one PR
- No direct commits on `main` for implementation work
- Orchestrator **never merges** without your explicit `merge`
- PR body documents agent-generated vs manual changes and test results
- PR checks run automatically after PR create — no manual CI verification needed

## Related Docs

- [README.md](README.md) — project overview and quick start
- [spec.md](spec.md) — full technical specification
- [implementation-workflow.mdc](.cursor/rules/implementation-workflow.mdc) — branch naming, PR templates, agent chain details
- [pr-checker agent](.cursor/agents/pr-checker/agent.md) — CI polling, SonarCloud, merge readiness
