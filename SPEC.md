# SPEC — Amadeus Micro Agent

> A multi-capability job-seeking chatbot agent.
> **Architecture-first**: the point of v1 is a container in which capabilities can exist
> and later elaborate — not a complete feature set.

Status: **Draft — awaiting approval**
Budget: **~14 hours** (revised from 8; quality over speed; +30m deployment plan; +30m
reliability/observability floor)
Date: 2026-07-29

---

## 1. Objective

Build a working, minimal, end-to-end job-seeking agent whose *architecture* is
production-shaped, while most of its *capabilities* are deliberately stubbed.

**Primary goal (architecture).** A pluggable capability registry where each capability is a
registered agent tool. Promoting a stub to a real feature must mean rewriting one function
body — never touching routing, the registry, the data layer, or the frontend.

**Secondary goals.** Practice a full SDLC at minimum depth (spec → plan → build → test →
review → ship), and build fluency with the loaded skill plugins. Neither gets separate
budget; both are practiced *during* the build.

**Target user.** A job seeker (initially the author) who wants one conversational surface for
resume management, job search, application tracking, strategy, and encouragement.

### Definition of done for v1

A user opens a web page, uploads a resume PDF, types a message, and gets a streamed reply
from an agent that:
1. routes to one of five registered capabilities,
2. ingests the PDF — validate → extract → decompose — and persists typed credentials to
   Postgres via a repository interface,
3. asks for approval before any write, describing the change in intent terms,
4. has an eval harness proving routing and extraction work, and
5. fails loudly and recoverably — API, DB, or subprocess failures surface as structured
   chat messages, never a hung stream, silent crash, or lost data.

---

## 2. Budget and deferral list

Budget revised from 8 to **~14 hours** by explicit decision: quality and a complete
engineering process outrank speed, plus a cloud deployment plan (document only) and a
reliability/observability floor (§10 — its ~30m of build cost lands inside phases 3 and 6,
where the error envelope, logging, and timeouts are written). The number is pinned rather than left as "a few more
hours" — an unbounded budget is the failure mode this section exists to prevent.

Plan for **2–3 sessions**, not one sitting. Phase boundaries are the checkpoints.

| # | Phase | Box | Cumulative |
|---|-------|-----|-----------|
| 0 | Preflight: CLI, SDK, Docker, PDF libs | 25m | 0:25 |
| 1 | Spec (this doc) | 25m | 0:50 |
| 2 | Plan / task breakdown | 30m | 1:20 |
| 3 | **Walking skeleton** — FastAPI + SDK + 1 stub tool + React shell | 120m | 3:20 |
| 4 | Persistence: Postgres, migrations, repositories | 90m | 4:50 |
| 5 | **Document ingestion** — upload → validate → extract → OCR fallback | 150m | 7:20 |
| 6 | `resume_store` real + remaining stubs + approval gate | 90m | 8:50 |
| 7 | Eval + test harness | 75m | 10:05 |
| 8 | Review | 60m | 11:05 |
| 9 | UI pass (`impeccable`) | 60m | 12:05 |
| 10 | Ship docs: README, ADR, fine-tuning proposal, deployment plan | 90m | 13:35 |

### Deferral list — in order, no debate at defer time

The cut list is now a **deferral** list: these are postponed to a later session rather than
dropped, because the complete process is the goal. Order still binds.

1. **OCR fallback.** Text-layer extraction covers digital-native PDFs, which is the large
   majority. Tesseract is a system binary and the single most likely time sink in phase 5.
2. **UI pass (phase 9).** Functional-but-plain ships; `impeccable` is a discrete later pass.
3. **`emotional_support` + `job_search_match`.** The registry proves extensibility at 3.
4. **pgvector / embeddings.** Columns exist in schema, stay unpopulated.
5. **Postgres → SQLite.** Only if Docker exceeds its preflight box.

### Escalation rule (unchanged)

If any phase exceeds its box by >25%, defer the next item immediately. Do not extend the
box. Do not renegotiate mid-phase. A larger budget does not relax this rule — it is the
mechanism that keeps 13 hours from becoming 40.

---

## 3. Architecture

```
┌─────────────────────┐
│ React + Vite + TS   │  chat UI, SSE stream, file upload, approval prompts
└──────────┬──────────┘
           │ HTTP + SSE
┌──────────▼──────────────────────────────────────────┐
│ FastAPI                                             │
│  ├── POST /api/chat        stream agent messages    │
│  ├── POST /api/documents   upload a resume          │
│  ├── POST /api/approvals/{id}  resolve a gate       │
│  ├── GET  /api/health                               │
│  │                                                  │
│  ├── AgentService ──── ClaudeSDKClient (session)    │
│  │      └── can_use_tool ──> ApprovalGate           │
│  │                                                  │
│  ├── Ingestion pipeline                             │
│  │      validate → BlobStore → extract → [OCR] →    │
│  │      decompose → CredentialRepository            │
│  │                                                  │
│  ├── Capability registry (in-process MCP server)    │
│  │      resume_store        REAL                    │
│  │      strategy_convo      stub → raw LLM          │
│  │      application_track   stub → raw LLM          │
│  │      job_search_match    stub → raw LLM          │
│  │      emotional_support   stub → raw LLM          │
│  │                                                  │
│  └── Repositories (interfaces)                      │
│         CredentialRepository → Postgres             │
│         BlobStore            → local filesystem     │
└─────────────────────────────────────────────────────┘
                    │                    │
              ┌─────▼─────┐      ┌───────▼────────┐
              │ Postgres  │      │ ./data/blobs/  │
              │ (docker)  │      │ (→ S3 later)   │
              └───────────┘      └────────────────┘
```

### Key decisions

| Decision | Choice | Rationale |
|---|---|---|
| Agent runtime | **Claude Agent SDK (Python)** | Agent loop, sessions, tools, permissions provided |
| Client primitive | **`ClaudeSDKClient`** | Retains session context across turns; supports `interrupt()`. `query()` is one-shot and wrong for chat |
| Capability transport | **In-process MCP** via `create_sdk_mcp_server()` | No subprocess, no network hop; capabilities are plain async Python |
| Web framework | **FastAPI** | Async-native — matches the SDK's async message stream; SSE is natural |
| Relational store | **Postgres 16** | Data is genuinely relational; JSONB absorbs schema churn; pgvector reserved for matching |
| Blob store | **Local filesystem** behind `BlobStore` | PDFs never belong in DB rows; interface makes S3/MinIO a one-class swap |
| PDF extraction | **pdfplumber** text layer, **OCR as detected fallback** | Most resumes are digital-native; OCR (Tesseract system binary) engages only when extraction yields near-zero text. Deferral item 1 |
| Decomposition | **LLM-based** (structured output), not regex | Resume layouts are too diverse for rules; the LLM maps extracted text → typed credentials |
| Model | **`claude-sonnet-5`** | Cost/latency fit for chat; escalate specific capabilities to Opus later if evals justify |

### Known constraints (verified against official docs, 2026-07-29)

- **The Python SDK requires the Claude Code CLI installed.** It spawns the CLI as a
  subprocess and communicates via JSON over stdin/stdout. This is a deployment
  dependency, not just a dev one. Verified in phase 0.
- **API-key auth is required** for SDK-built products. claude.ai login is not permitted for
  third-party products built on the Agent SDK.
- No Node.js runtime dependency for the Python SDK itself (Vite needs Node for the
  frontend build, separately).

### Cloud deployment path (plan only — nothing implemented in v1)

Requirement: the local architecture must be verifiably cloud-portable, so this is not a
toy project. Deliverable: `docs/deployment-plan.md` in phase 10. The mapping that makes it
workable:

| Local piece | Cloud target | Migration cost |
|---|---|---|
| React + Vite build | Static hosting/CDN (Vercel, Cloudflare Pages, S3+CloudFront) | `npm run build` output is already static; near-zero |
| FastAPI backend | **Container** on Cloud Run / Fly.io / ECS | Dockerfile; the one real constraint is below |
| Postgres (docker-compose) | Managed Postgres (Neon, Supabase, RDS) — pgvector supported on all three | Change `DATABASE_URL`; migrations already via Alembic |
| Blob store (local FS) | S3 / R2 / GCS | Swap the `BlobStore` implementation — the interface exists precisely for this |
| Secrets (.env) | Platform secret manager | Config already isolated in `pydantic-settings` |

**The one non-standard constraint:** the Python Agent SDK spawns the Claude Code CLI as a
subprocess, so the backend image must install the CLI (a Node-based binary) alongside
Python. This rules out "serverless function per request" deployment shapes and means the
backend ships as a **container with both runtimes**, sized with enough memory for the CLI
subprocess. Verified as a supported pattern; the deployment plan documents the Dockerfile
sketch. Session state lives in the SDK subprocess, so v1's plan targets a single container
instance (or sticky sessions) — horizontal scaling is a documented future concern, not a
v1 problem.

Architecture consequences already absorbed: repository protocols, `BlobStore` interface,
env-only config, and stateless HTTP + SSE (no websockets requiring special infra). No v1
code change is needed for any row in the table — which is the point of the check.

### Future evolution (documented, not built)

A capability graduates from **tool → subagent** when it needs its own system prompt and
context window. `strategy_convo` is the first candidate: multi-turn strategy with
intelligent follow-ups outgrows a single tool call. The registry is designed so this
does not change the calling contract.

---

## 4. Capabilities

All five register as tools, exposed as `mcp__jobseeker__<name>`. Every stub shares one
implementation shape, so promotion is a body rewrite.

| Capability | v1 | Contract |
|---|---|---|
| `resume_store` | **REAL** | Ingest resume text/PDF → decompose into typed credentials → persist via repository. Returns a summary of what was stored. |
| *(pipeline)* | **REAL** | Document ingestion is not itself a capability but the pipeline `resume_store` calls: validate (MIME, size ≤10 MB, magic bytes) → store blob → extract text layer → OCR fallback if near-empty → LLM decomposition → repository writes behind one approval. |
| `strategy_convo` | stub | Career strategy with follow-up questions. Raw LLM call, strategy-specific system prompt. |
| `application_track` | stub | Record/query application status. Raw LLM call; schema exists but unused in v1. |
| `job_search_match` | stub | Match stored credentials to postings. Raw LLM returns plausible matches; no external data source in v1. |
| `emotional_support` | stub | Encouragement and reframing. Prompt persona only. Proves the container handles non-task capabilities. |

### Stub contract

```python
@tool(name, description, schema)
async def capability(args: dict[str, Any]) -> dict[str, Any]:
    """STUB — replace body with real implementation. Contract is stable."""
    text = await raw_llm(system=CAPABILITY_PROMPT, user=args["query"])
    return {"content": [{"type": "text", "text": text}]}
```

Each stub carries a `# STUB:` marker and a docstring naming its promotion path.

---

## 5. Data model

```sql
candidate(id, name, contact JSONB, created_at)
credential(id, candidate_id, kind, title, org, start_date, end_date,
           body JSONB, embedding vector(1536) NULL)
document(id, candidate_id, kind, uri, sha256, mime_type, size_bytes,
         page_count, extraction_method, status, uploaded_at)   -- blob pointer
job(id, source, title, company, jd_text, raw JSONB, embedding vector(1536) NULL)
application(id, candidate_id, job_id, status, applied_at)
application_event(id, application_id, event_type, payload JSONB, at)  -- append-only
conversation(id, candidate_id, sdk_session_id, started_at)
message(id, conversation_id, role, content JSONB, at)
approval(id, conversation_id, tool_name, args JSONB, decision, decided_at)
```

`kind` on `credential` ∈ `experience | education | skill | project | certification`.
`extraction_method` on `document` ∈ `text_layer | ocr`; `status` ∈ `uploaded | extracted |
decomposed | failed`. Recording the method matters — OCR output is materially noisier, and
downstream confidence should reflect that.
`application_event` is the append-only growth table — the "massive state data" driver.
Vector columns are created but unpopulated in v1 (deferral item 4).

---

## 6. Commands

```bash
# Preflight
claude --version                  # SDK requires the CLI
docker compose up -d db           # Postgres on :5432

# Backend
uv sync                           # or: pip install -e .
uv run alembic upgrade head       # schema
uv run fastapi dev app/main.py    # :8000

# Frontend
npm install
npm run dev                       # :5173, proxies /api → :8000

# Quality
uv run pytest                     # unit + integration
uv run pytest tests/evals -m eval # capability routing evals
uv run ruff check . && uv run ruff format --check .
uv run mypy app
npm run typecheck && npm run build
```

---

## 7. Project structure

```
Amadeus-Micro-Agent/
├── SPEC.md  PRODUCT.md  README.md
├── docs/adr/0001-*.md            # decision records
├── docs/fine-tuning-proposal.md
├── docker-compose.yml
├── backend/
│   ├── pyproject.toml
│   ├── alembic/versions/
│   └── app/
│       ├── main.py               # FastAPI app + routes
│       ├── config.py             # pydantic-settings
│       ├── agent/
│       │   ├── service.py        # ClaudeSDKClient lifecycle
│       │   ├── approvals.py      # can_use_tool gate
│       │   └── prompts.py
│       ├── capabilities/
│       │   ├── registry.py       # create_sdk_mcp_server
│       │   ├── resume_store.py   # REAL
│       │   └── stubs/            # one file per stub
│       ├── ingestion/
│       │   ├── validate.py       # MIME, size, magic bytes
│       │   ├── extract.py        # pdfplumber text layer
│       │   ├── ocr.py            # Tesseract fallback (deferral item 1)
│       │   └── decompose.py      # LLM text → typed credentials
│       ├── repositories/
│       │   ├── base.py           # Protocol interfaces
│       │   ├── credential_pg.py
│       │   └── blob_fs.py
│       └── models/               # SQLAlchemy
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── components/{ChatWindow,MessageList,ApprovalPrompt}.tsx
│       └── lib/sse.ts
└── tests/
    ├── unit/  integration/  evals/
```

---

## 8. Code style

**Python** — 3.12+. Ruff (lint + format), line length 100. `mypy` strict on `app/`. Full type
annotations; `async def` throughout the agent path. Pydantic for all I/O boundaries.
Repositories are `Protocol` classes — capabilities depend on the protocol, never a concrete
implementation. No business logic in route handlers.

**TypeScript** — strict mode, no `any`. Function components + hooks. No state library in v1;
`useState` + `useReducer` suffice. No CSS framework (cut-list item 1).

**General** — every stub marked `# STUB:` with its promotion path. Conventional Commits.
No secrets in source; `ANTHROPIC_API_KEY` via env only.

---

## 9. Testing strategy

Three tiers, deliberately thin (60-minute box).

**Unit (`tests/unit/`)** — capability contract shape, credential decomposition, repository
interface conformance against an in-memory fake, and ingestion validation (rejects
oversized/wrong-MIME/corrupt files; text-layer vs. scan detection against synthetic PDF
fixtures). Fast, no network, no DB.

**Integration (`tests/integration/`)** — FastAPI routes via `httpx.ASGITransport`; repository
implementations against a real Postgres (testcontainers or the compose DB); SSE stream
yields well-formed events. Agent SDK mocked at the client boundary.

**Evals (`tests/evals/`, `-m eval`)** — the tier that actually matters for an agent. A golden
set of ~15 utterances mapped to expected capability routing:

| Utterance | Expected |
|---|---|
| "Here's my resume, can you save it?" | `resume_store` |
| "I'm burnt out on rejections" | `emotional_support` |
| "Should I target startups or big tech?" | `strategy_convo` |

Scored as routing accuracy; threshold **≥80%**. Excluded from the default `pytest` run
because they cost tokens and are non-deterministic. This harness is the deliverable —
a growing golden set is what makes stub promotion safe later.

**Not in v1:** load testing, E2E browser tests, mutation testing, frontend component tests.

---

## 10. Engineering quality attributes

Scaled to v1: every target is measurable and cheap at single-user scope. Formal SLOs
(uptime %, p99 under load) are explicit **non-goals** — a local single-user app has no
meaningful uptime number. What "reliability" means here instead: **the system never loses
user data, and it fails loudly and recoverably.**

### Reliability

| Concern | v1 target | Mechanism |
|---|---|---|
| Anthropic API outage/error | Readable error message in chat; never a hung stream or crash | Error envelope on the SSE stream; timeout on every SDK call |
| SDK subprocess dies | Next message gets a fresh session + a "conversation restarted" notice | Health-check on `ClaudeSDKClient`; recreate on failure |
| DB unavailable | Request fails with 503 + clear message; no partial writes | Connection retry (3×, backoff); repository ops transactional |
| Duplicate resume upload | Idempotent — same file never double-ingests | `sha256` dedupe on `document` (column already in schema) |
| Ingestion fails mid-pipeline | No orphaned state; `document.status = failed` with reason | Pipeline stages update status; credentials commit atomically at the end |
| External call hangs | Nothing waits forever | Explicit timeout on every outbound call (SDK, DB, OCR) |

### Observability

- **Structured JSON logs** from the first skeleton commit: every request carries a
  `request_id`; every agent turn carries a `session_id`; every tool invocation logs
  name, duration, and outcome. No PII (resume content) in log lines — log IDs and counts.
- **Audit trail** — the `approval` table already records every write decision (§10 was
  designed for this; it doubles as an observability surface).
- **`GET /api/health`** — reports DB reachability and SDK subprocess liveness, not just 200.
- **Deferred, documented:** metrics endpoint (Prometheus/OTel), tracing. Named in the
  deployment plan as the first post-v1 observability step.

### Performance (budgets, not SLOs)

- First streamed token after user message: **< 5 s** typical.
- Resume ingestion (upload → credentials proposed): **< 60 s** for a 2-page text-layer PDF.
- These are logged (see above) so regressions are visible, but not enforced by CI in v1.

### Cost

- Token spend is an engineering metric here: `max_tokens` capped per capability call;
  evals (`-m eval`) excluded from default test runs; model choice (Sonnet) is itself a
  cost decision recorded in §3.

### Security (v1-scope)

- Upload validation as specified (§4); CORS locked to the frontend origin; API key via
  env only; synthetic fixtures only in tests. Auth is a non-goal (single user, §11).

### Verification

Reliability rows are tested where cheap: unit tests for dedupe and status transitions;
integration tests simulate DB-down and SDK-error paths (mock boundary). The API-outage
and subprocess-death rows get one manual verification each during phase 8 review, recorded
in the review notes.

## 11. Boundaries

### Always
- Ask before **any** write — filesystem, database, or outward-facing. (User decision.)
- Log every tool invocation and approval decision to the `approval` table.
- Keep all agent file access inside `./data/`.
- Depend on repository *protocols*, never concrete implementations.
- Keep stub contracts stable — promotion changes bodies only.

### Ask first
- Any outward-facing action: send, email, submit, post, apply.
- Any schema migration.
- Any new third-party dependency.
- Any spend beyond routine model calls.

### Never
- Commit secrets or real personal resume data. Fixtures are synthetic.
- Store PDFs as database rows — blobs go to `BlobStore`.
- Let a capability import another capability. All coordination is through the agent loop.
- Auto-apply to a job, or send anything on the user's behalf, under any circumstance in v1.
- Bypass the approval gate, including "just for testing."

### Implementation note on "ask before every write"

Approval is granted at **capability-batch granularity**, not per row. Ingesting one resume
produces ~20 credential writes; 20 separate prompts would make the tool unusable. The
capability declares its intended write set, the user approves once, and each individual
write is still recorded in the audit log. This preserves the guarantee — nothing is written
without consent — without prompt fatigue.

**Approval requests are descriptive, not literal.** The prompt states *intent* in the user's
terms, never a dump of raw payload or a full-text diff:

> ✅ "Can I rewrite your Anthropic experience bullets to be more concise and
> metric-driven? (3 bullets affected)"
> ❌ *[displays 400 characters of before/after JSON]*

Every `ApprovalRequest` therefore carries a required `intent: str` — a one-line, plain-language
summary — alongside the machine payload. The payload is available on expand for users who
want it, and is always written to the `approval` audit row, but the summary is what the
prompt shows. A capability that cannot describe its own write in one sentence is doing too
much and should be split.

---

## 12. Open questions

1. ~~Resume PDF parsing~~ — **Resolved: enabled.** Upload → validate → extract (text layer,
   OCR fallback) → decompose → store. See §3 ingestion pipeline.
2. **Multi-user** — v1 assumes a single local candidate; no auth. Confirm acceptable.
3. **Session persistence across restarts** — SDK session resume vs. rebuild from `message`
   table. Deferred to phase 4.
4. **Embedding model** — deferred with pgvector (deferral item 4).

---

## 13. Approval

- [ ] Objective and definition of done
- [ ] Budget reality and binding cut list
- [ ] Architecture and key decisions
- [ ] Capability roster and stub contract
- [ ] Data model
- [ ] Testing strategy
- [ ] Boundaries
