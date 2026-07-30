---
name: agent-id-kebab-case
description: 1-2 sentences — WHEN to delegate (routing signal), WHAT this agent does. Be specific, not vague.
model: claude-sonnet-4.5
temperature: 0.1
readonly: false
is_background: false
---

# Agent Display Name

## Mission

[1-2 sentences: role and primary outcome. State what this agent does **NOT** do — e.g. does not merge PRs, does not implement features.]

## When to invoke

| Trigger | Invoker | Action |
|---------|---------|--------|
| [user command or orchestrator step] | [user / @phase-orchestrator / other] | [what to run] |

## Inputs

| Input | Required | Source |
|-------|----------|--------|
| [file, branch, phase #, prior report, env] | yes/no | [path or how obtained] |

Reference docs (do not duplicate): [`spec.md`](../../spec.md), [`WORKFLOW.md`](../../WORKFLOW.md).

## Workflow

1. **[Step name]** — [mandatory action with concrete command or file to read]
2. **[Step name]** — [mandatory action]
3. **[Step name]** — [mandatory action]
4. **Report** — fill Output format below; do not proceed past BLOCKED without escalation rule.

## Output format

```markdown
# [Agent Name] Report

## Summary
[1-2 sentences with overall ✅ / ⚠️ / ❌]

## [Section-specific results]
- ✅ [passed item]
- ⚠️ [warning item]
- ❌ [failed item]

## Recommendation
- ✅ **PASS** — [condition]
- ⚠️ **CONDITIONAL** — [condition]
- ❌ **BLOCKED** — [condition]

## Next steps
[Concrete actions or @agent handoff]
```

## Decision rules

| Outcome | Condition | Action |
|---------|-----------|--------|
| **PASS** | [criteria] | Return report; orchestrator continues |
| **CONDITIONAL** | [criteria] | Return report with warnings; orchestrator may continue |
| **BLOCKED** | [criteria] | Stop; escalate to @other-agent or user |
| **Escalate** | [criteria] | @agent-name with full context |

## Constraints

- Never [forbidden action — e.g. auto-merge, force-push main, skip mandatory step].
- Max [N] fix/retry loops when applicable.
- Touch only files required for this agent's job.
- Do not duplicate full `spec.md` — reference sections by name.

## Examples

### Good

**Input:** [concrete scenario]  
**Output:** [brief expected report headline — PASS with scores]

### Bad

**Input:** [concrete scenario]  
**Output:** [what not to do — e.g. "QA passed" without running Set B]
