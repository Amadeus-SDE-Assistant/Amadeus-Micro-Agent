# Amadeus — a job-search agent that asks before it acts

Amadeus is a personal job-seeking agent: one chat surface where you can upload a
resume and watch it decompose into structured credentials, talk through search
strategy, track applications, and get through the rough days of a search. It's built
on the Claude Agent SDK — and it **never writes anything without asking you first, in
plain language**:

> **Amadeus asks permission**
> *Decompose the resume text you shared (~29 words) into structured credentials and
> save them to your profile?*
> `[ Approve ]` `[ Deny ]`

Deny it, and nothing is written — verified down to the database row. Every decision
(approved, denied, or expired) lands in an audit table, linked to its conversation.
Consent isn't a dialog box bolted on at the end; it's the product's architecture.

## Why this repo is worth your five minutes

**1. An agent architecture designed to grow, demonstrated small.** Five capabilities
register as tools on an in-process MCP server. One (`resume_store`) is real; four are
deliberate, honest stubs — a raw LLM call behind a stable contract, each marked with
its promotion path. Promoting a stub to a real feature means rewriting one function
body. Routing, storage, approval gating, and the frontend don't move. A 94%-accuracy
routing eval (16 golden utterances, ~$0.25 a run) is the regression net that makes
promotion safe.

**2. A security lesson you can only learn live.** The first approval demo wrote to
the database with *no prompt*: the SDK's `allowed_tools` list bypasses the
`can_use_tool` permission callback entirely. Forty-six green unit tests missed it;
a live browser demo caught it. The fix, the regression test, and the full story are
in [ADR-0002](docs/adr/0002-approval-design.md).

**3. The complete engineering process, in the repo.** This was built spec-first in
~13 hours against a pinned budget, and every artifact of that process ships here:
[the spec](SPEC.md) with amendment markers where reality won arguments, [the plan](tasks/plan.md)
with per-task acceptance criteria and actual-vs-box times, a [two-axis review](docs/review/P8-review-notes.md)
with explicit waivers, reliability checks passed by *killing the agent subprocess
mid-turn*, [ADRs](docs/adr/), a [fine-tuning proposal](docs/fine-tuning-proposal.md)
whose evidence-based verdict is *"not yet — here are the four triggers that reopen
it"*, and a [deployment plan](docs/deployment-plan.md). The [dev log](docs/devlog.md)
tells the day's story, bugs and all.

## Stack

React + Vite + TypeScript · FastAPI (Python 3.12) · Claude Agent SDK
(`ClaudeSDKClient`, in-process MCP, `can_use_tool`) · PostgreSQL 16 + pgvector ·
SSE streaming · repository Protocols with symmetric in-memory/Postgres conformance
tests.

```
Browser ──SSE──▶ FastAPI ──▶ AgentService ──▶ Claude Agent SDK (bundled CLI subprocess)
                    │              │                    │
                    │        ApprovalGate ◀── can_use_tool (write capabilities only)
                    │              │
              Ingestion       Capability registry (in-process MCP)
              pipeline          resume_store · strategy · tracking · matching · support
                    │
              Postgres + blob store (behind swap-ready Protocols)
```

## Run it

Prereqs: Docker, [uv](https://docs.astral.sh/uv/), Node 20+, and either a Claude Code
login on the machine or `ANTHROPIC_API_KEY` in the environment (the SDK bundles its
own CLI — nothing else to install).

```bash
docker compose up -d db          # Postgres on host :5433

cd backend
uv sync
uv run alembic upgrade head
uv run python run.py             # :8000 — not uvicorn --reload; see ADR-0001
```

```bash
cd frontend
npm install
npm run dev                      # :5173
```

Open http://localhost:5173 and try:

- *"Should I target startups or big tech?"* → routes to the strategy capability
- *"Save this to my profile: <paste a few resume lines>"* → the approval card appears;
  deny it once, just to watch nothing happen
- Upload a PDF resume → watch it move through `uploaded → extracted → decomposed →
  stored`, credentials appearing as they land

## Quality

```bash
cd backend
uv run pytest                       # 51 unit tests — fast, no tokens, no DB
uv run pytest -m integration        # dedicated amadeus_test database
uv run pytest tests/evals -m eval   # routing eval vs the REAL agent (~$0.25)
uv run ruff check . && uv run mypy  # lint + strict typing, both clean
```

Routing eval: **94%** ([report](backend/tests/evals/REPORT-2026-07-30.md)). Reliability
is tested by breaking things: a dead Anthropic endpoint yields a readable error (never
a hung stream), and a killed agent subprocess recovers with a fresh session and a
visible notice.

## Status & roadmap

v1 is closed and honest about its edges: chat history persists but doesn't yet
re-render on reload, OCR is deferred until a real scanned resume shows up, and stubs
advise but don't store. The promotion ladder and full roadmap live in
[docs/v1-summary.md](docs/v1-summary.md).

## License

MIT — see [LICENSE](LICENSE).
