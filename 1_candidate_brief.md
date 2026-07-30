# Build Exercise — Bug Report Triage Service

## What this is

We build software in a heavily agent-driven way: specs live in markdown, agents do
most of the typing, and engineers spend their time steering, reviewing, and hardening
what the agents produce. This exercise is designed to look like a normal day of that work.

**You may use AI/agents freely — that is the job, not cheating.** We are not testing
whether you can write code from memory. We are testing whether you can build a
*trustworthy* system on top of an unreliable component (an LLM), steer it when it drifts,
and know where it will break.

## Time & format

- **Prep (async, on your own time — aim for ~2–3 hrs, not a full weekend):** build the
  core service described below. Come with something running. You'll have up to ~1 week from
  receiving this brief.
- **Onsite (~2 hrs):** you'll walk us through it, we'll extend the requirements live, and
  we'll finish with a short discussion. Bring your working environment; we'll run it together
  (in person, or remote over Zoom if that's easier logistically).

You will not be graded on polish or on finishing everything. We care far more about
how you reason about failure than about how much you shipped.

## The task

Build a service that turns a **free-text bug report** into a **structured, triaged issue**
in a self-hosted **Gitea** instance.

Given a raw report (a paragraph a user or teammate typed), your service should:

1. Produce a concise **title**.
2. Assign a **severity**: `critical` | `high` | `medium` | `low`.
3. Assign one or more **component labels** from: `frontend`, `backend`, `api`, `auth`,
   `database`, `infra`, `docs`, `unknown`.
4. Extract **clean reproduction steps** (or record that none were provided — do not invent them).
5. Check for **duplicates** against existing open issues. If it's clearly a duplicate,
   do not open a new issue — link/annotate the existing one instead.
6. Create the issue in Gitea (or, for a confident duplicate, comment on the existing one).

Input can arrive however you like — an HTTP endpoint or a CLI both fine.

## Infrastructure — you stand it up

Please **`docker-compose` the whole thing yourself**, including Gitea and anything else
you decide you need. We want to see you bring a working system up from nothing and add
only what the task warrants.

- Gitea: run it locally via Docker, create a repo, seed it with the existing issues we
  provide (see the sample data file) so your duplicate check has something to work against.
- LLM access: we'll provide an API key for the exercise — you'll receive it with this brief.
  Use it for both the prep and the onsite; no need to bring your own.
- Framework: **your choice.** Part of what we're interested in is what you reach for and why.
  Plain SDK calls are fine; agentic frameworks (e.g. LangChain/LangGraph, LlamaIndex,
  the Vercel AI SDK, Pydantic AI, or an MCP-based setup) are equally welcome — none are
  required or preferred. Reach for what lets you build a trustworthy system fastest.

## Ground rules

- Commit your work to the Gitea repo and open at least one PR — we want to see the flow
  end to end, not just a script on your laptop. Use the PR description to note what the
  agent generated, what you changed, and what you didn't trust — that's the review step
  we care about, not the PR ceremony itself.
- Keep a short `README` / `spec.md` describing how you drove this and any decisions you made.
- It's fine to leave TODOs and rough edges. Note them.

## What to expect onsite

- A short walkthrough from you: what it does, how you built it, what you'd trust and what you wouldn't.
- We'll **change or add a requirement** and work on it together, live.
- We'll run your service against **inputs you haven't seen** and look at how it behaves.
- A closing conversation about where this would break in production.

## How we evaluate (honest version)

We are looking at the engineering *around* the LLM, because the LLM's raw output is never
the deliverable. Concretely, we care about things like:

- Does it always return well-formed, valid output — or can it emit garbage structure?
- What happens on weird, empty, hostile, or off-topic input?
- Does it degrade gracefully and flag uncertainty, or confidently make things up?
- Does the duplicate check actually work — and does it avoid *false* merges?
- Can you explain what the agent got wrong while you built it, and how you caught it?

If you find yourself thinking "how would I even know if this is right?" — good. That
question is most of the job. We'd love to see your answer to it built into the system.
