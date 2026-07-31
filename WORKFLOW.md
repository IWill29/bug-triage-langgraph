# Implementation Workflow

You drive the project with **one command**. The [phase-orchestrator](.cursor/agents/phase-orchestrator/agent.md) runs the full agent chain automatically — no manual `@agent` picks at each step.

## What You Say

| Command | What happens |
|---------|--------------|
| **`start phase 2`** | Full pipeline for Phase 2: branch → implement → audit → QA → fix loops → PR |
| **`next`** / **`continue`** | Same pipeline for the next unchecked phase (currently Phase 4) |
| **`merge`** / **`merge pr`** | Squash-merge the open phase PR (only when you approve) |
| **`status`** | Phase checklist, open PRs, last audit/QA summary |
| **`check pr`** | CI status for open phase PR (SonarCloud App + other checks) — no merge |

Example session:

```
You:  next
Agent: [creates phase-2-workflow-nodes, implements, audits, tests, opens PR]
Agent: PR #4 ready — QA 8/8, auditor pass. Say "merge" when ready.

You:  merge
Agent: [squash-merges PR, updates checklist]
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
         └─ 8. Report PR URL        does NOT merge unless you say "merge"
```

## Agent Roles

| Agent | When | Job |
|-------|------|-----|
| **phase-orchestrator** | You say start/next/continue/check pr | Runs entire pipeline, delegates everything |
| **generalPurpose** | Every phase step 2 | Implements code from spec + langgraph-bug-triage skill |
| **spec-architect** | spec.md changed | Validates architecture before merge |
| **code-auditor** | Every phase step 4 | Audits code vs `spec.md` — **mandatory** |
| **qa-tester** | Every phase step 5 | Phase 1: Docker/Gitea/DB/LLM; Phase 2+: Set B — **mandatory** |
| **bug-fixer** | Audit or QA failures | Fixes issues, triggers re-audit or re-test |

You never invoke these directly during normal phase work — the orchestrator does.

## Phase Status

- [x] **Phase 0:** Architecture (on `main`)
- [x] **Phase 1:** Infrastructure (merged [PR #2](https://github.com/IWill29/bug-triage-langgraph/pull/2))
- [x] **Phase 2:** Workflow nodes (merged [PR #6](https://github.com/IWill29/bug-triage-langgraph/pull/6) → `2bddf5b` on `main`)
  - CI: SonarCloud ✅ | CodeRabbit ✅ | unit tests 15/15 ✅
  - QA: **partial** — Set B live deferred; full validation planned Phase 4
- [x] **Phase 3:** Production hardening (merged [PR #7](https://github.com/IWill29/bug-triage-langgraph/pull/7) → `826c38d` on `main`)
  - CI: SonarCloud ✅ | unit + integration 28/28 ✅ (mocked)
  - QA: **partial** — live Set B 0/7; deferred to Phase 4
- [ ] **Phase 4:** Testing — **NEXT** (`phase-4-testing`)

Say **`next`** or **`start phase 4`** for full Set B validation + integration test coverage. Optional: start Docker + set `GITEA_TOKEN`/`DB_PASSWORD` for live QA.

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

## Related Docs

- [README.md](README.md) — project overview and quick start
- [spec.md](spec.md) — full technical specification
- [implementation-workflow.mdc](.cursor/rules/implementation-workflow.mdc) — branch naming, PR templates, agent chain details
