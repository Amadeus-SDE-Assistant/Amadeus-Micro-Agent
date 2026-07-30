# Amadeus Micro Agent

A multi-capability job-seeking chatbot agent, built architecture-first: a pluggable
capability registry on the Claude Agent SDK where most capabilities are deliberate
stubs that promote to real features without touching routing, storage, or the
frontend. Every agent-initiated write passes a descriptive, human-approved gate with
a full audit trail.

**Stack:** React + Vite + TypeScript · FastAPI (Python 3.12+) · Claude Agent SDK ·
PostgreSQL 16 + pgvector (Docker) · filesystem blob store behind a swap-ready interface.

**Capabilities (5 registered):** `resume_store` (real — PDF/text → structured
credentials, writes gated by approval) · `strategy_convo` · `application_track` ·
`job_search_match` · `emotional_support` (stubs: raw LLM calls with capability
prompts, identical contract, promotion-ready).

See [SPEC.md](SPEC.md) for the full design, [tasks/plan.md](tasks/plan.md) for how it
was built, and [docs/](docs/) for ADRs, the review record, the fine-tuning proposal,
and the deployment plan.

## Prerequisites

- **Docker** (for Postgres)
- **uv** (Python package manager)
- **Node 20+** (frontend build)
- **Anthropic auth**: either an existing Claude Code login on the machine, or
  `ANTHROPIC_API_KEY` set in the environment. The Agent SDK bundles its own Claude
  Code CLI binary — no separate CLI install is required.

## Run it

```bash
# 1. Database (host port 5433 — 5432 is deliberately left free)
docker compose up -d db

# 2. Backend  (http://localhost:8000)
cd backend
uv sync
uv run alembic upgrade head
uv run python run.py
```

```bash
# 3. Frontend (http://localhost:5173, proxies /api -> :8000)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Try: *"Should I target startups or big tech?"* (routes to
the strategy capability), or paste resume text with *"save this to my profile"* and
watch the approval card — nothing is written until you approve. Upload a PDF resume in
the panel below the chat.

> **Windows note:** the backend must start via `run.py` (not `uvicorn --reload` or
> `fastapi dev`) — the Agent SDK spawns a subprocess, which requires the Proactor
> event loop that reload mode replaces. See ADR-0001.

## Quality gates

```bash
cd backend
uv run pytest                 # 51 unit tests (fast, no tokens, no DB)
uv run pytest -m integration  # against a dedicated amadeus_test DB (compose DB up)
uv run pytest tests/evals -m eval   # routing eval vs the REAL agent (costs ~$0.25)
uv run ruff check . && uv run mypy

cd frontend
npm run typecheck && npm run build
```

Current state: 51 unit + 4 integration green; routing eval **94%** (threshold 80% —
[report](backend/tests/evals/REPORT-2026-07-30.md)); ruff + mypy strict clean.

## Project layout

```
backend/app/
  agent/         AgentService (SDK session pool), ApprovalGate, prompts, events
  capabilities/  registry (in-process MCP server), resume_store, stubs/
  ingestion/     validate -> extract (pdfplumber) -> decompose (LLM) -> store
  repositories/  Protocol interfaces + Postgres and in-memory implementations
  routes/        chat (SSE), documents, approvals — thin handlers
frontend/src/    ChatWindow, MessageList, UploadPanel, SSE client
docs/            ADRs, review notes, fine-tuning proposal, deployment plan
tasks/           plan + checklist with actual-vs-box time tracking
```

## Design guarantees worth knowing

- **Consent is the product.** Write capabilities are excluded from `allowed_tools`
  (which would bypass the permission callback — ADR-0002) and pause the turn for a
  plain-language approval; every decision lands in the `approval` audit table.
- **Fails loudly, recovers quietly.** Errors arrive as readable chat messages; a dead
  SDK subprocess is dropped and the next turn announces the fresh session. Verified
  by killing the subprocess mid-turn ([review record](docs/review/P8-review-notes.md)).
- **Stubs are honest.** Every stub carries a `# STUB:` marker and its promotion path;
  the [routing eval](backend/tests/evals/test_routing.py) is the regression net that
  makes promotion safe.
