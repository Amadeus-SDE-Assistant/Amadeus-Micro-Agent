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
needs_ocr | decomposed | stored | failed` (P8 amendment: `needs_ocr` = clean stop when the
text layer is absent and OCR is deferred; `stored` = credentials committed). Recording the
method matters — OCR output is materially noisier, and downstream confidence should
reflect that.
`application_event` is the append-only growth table — the "massive state data" driver.
Vector columns are created but unpopulated in v1 (deferral item 4).

---

## 6. Commands

```bash
# Preflight
docker compose up -d db           # Postgres on host :5433 (P10: 5432 was taken;
                                  # the SDK bundles its own CLI — no claude install)

# Backend
uv sync                           # or: pip install -e .
uv run alembic upgrade head       # schema
uv run python run.py              # :8000 (P10 amendment: fastapi dev/--reload are
                                  # unusable — the SDK subprocess needs the Proactor
                                  # loop; see ADR-0001)

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

**General** — every stub marked `# STUB:` with its promotion path. Commits are
descriptive and task-prefixed (`T4.2: …`, `C6: …`) matching tasks/plan.md (P8
amendment — this replaced Conventional Commits in practice from the first commit;
recorded rather than rewritten). No secrets in source; `ANTHROPIC_API_KEY` via env
only (the compose dev DB password is local-only and explicitly not a secret).

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
  *P8 clarification:* for the REST upload path, the user's explicit upload action is
  the consent (the UI says so on the control); agent-initiated writes always go
  through the approval gate. Two entry paths, one guarantee.
- Log every **write** decision to the `approval` table; log every tool invocation
  (read or write) to the structured logs. (P8 amendment: the approval table is the
  write-audit; read-only invocations live in the JSON logs, where they carry
  request/session ids.)
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

- [x] Objective and definition of done — all 5 DoD items demonstrated live
      (C3 stream, C5 ingestion, C6 approvals, C7 evals 94%, C8 reliability checks)
- [x] Budget reality and binding cut list — final actuals in tasks/todo.md
- [x] Architecture and key decisions — as built; deviations carry P8/P10 amendments
- [x] Capability roster and stub contract — 5 registered, 1 real, 4 stubs marked
- [x] Data model — migrated, conformance-tested, audit-linked
- [x] Testing strategy — 51 unit + 4 integration + routing eval ≥80% (94%)
- [x] Boundaries — approval gate verified approve/deny/expire; audit rows live

v1 closed 2026-07-30 at checkpoint C10.

---

## 14. Phase 11 amendment — gap-closing pass

Opened 2026-07-30, after v1 close and merge to `main` (PR #2, `6027b90`). Not a new
project: three items already named in §12/docs/v1-summary.md as honest gaps, closed in
one small pinned increment before considering any "big upgrade." Same rules as §2 carry
over unchanged: pinned budget, binding order, >25% overrun defers the next item, no
box extension.

**Budget: ~3h**, new pinned number on top of v1's closed ~13h10.

| # | Task | Box | Cumulative |
|---|------|-----|-----------|
| 11.1 | Chat history re-render on reload | 35m | 0:35 |
| 11.2 | `application_track` promotion to a real write capability | 70m | 1:45 |
| 11.3 | OCR fallback (Tesseract) | 65m | 2:50 |

`emotional_support` — considered and dropped from scope: it already exists as a
registered raw-LLM stub (shipped Phase 6, `db5b71d`), which is exactly what was being
asked for. No task needed.

### T11.1 — Chat history re-render (35m)

`ConversationRepository.get_messages()` already exists and works in both
implementations (`repositories/postgres.py`, `repositories/memory.py`) — nothing calls
it. Add `GET /api/conversations/{id}/messages` + a `MessageOut`-shaped response, plus
client-side `conversationId` persistence (`ChatWindow.tsx` currently generates a fresh
random id every mount, never persisted) and a fetch-on-mount hydration path.
- **AC:** reload the page mid-conversation → prior messages re-render in order; no
  duplicate send; a conversation with zero messages still mounts cleanly.

### T11.2 — `application_track` promotion (70m)

Follows the `resume_store` pattern (`capabilities/resume_store.py`): pull
`CapabilityContext`, call a repository, return a summary. `Application`/
`ApplicationEvent` tables are already migrated, but `Application.job_id` is a
**non-nullable FK to `Job`**, and no `JobRepository` or `ApplicationRepository`
Protocol exists yet (`resume_store` only needed `CredentialRepository`) — this task
builds both.

**Design decision (approved 2026-07-30): no job dedup.** The tool takes
`{company, title, status, notes, application_id?}`. If `application_id` is given and
found, append an `ApplicationEvent` + update status. Otherwise create a **new** `Job`
row unconditionally (no fuzzy title/company matching) + `Application` + an initial
`ApplicationEvent`, and return the new `application_id` in the tool result so the
agent can reference it in later turns. Real job matching is explicitly out of scope
here — it belongs to `job_search_match`'s eventual promotion, not this task.

- Add `JobRepository` + `ApplicationRepository` Protocols (`repositories/base.py`) and
  Postgres + in-memory implementations, under the existing conformance suite pattern.
- Extend `CapabilityContext` (`capabilities/context.py`) with `jobs` / `applications`
  fields; wire in `main.py` alongside the existing `credentials` field.
- Rewrite `application_track` body per the design above.
- Register an intent builder in `registry.py`'s `_WRITE_INTENTS` — the `ApprovalGate`
  itself is already tool-agnostic (`agent/approvals.py`); no gate changes needed.
- **AC:** "I applied to X for a Y role" → one descriptive approval → `Job` +
  `Application` + `ApplicationEvent` rows persisted, audit row present; a follow-up
  turn referencing the returned `application_id` appends an event and updates status
  without creating a second `Job`/`Application`.

### T11.3 — OCR fallback (65m)

`needs_ocr` is a real, reachable terminal pipeline state
(`ingestion/extract.py` → `SCAN_THRESHOLD_CHARS`; handled in `ingestion/pipeline.py`)
with no downstream consumer. No `ocr.py` module, no `pytesseract`/Tesseract anywhere
in the codebase (confirmed by repo-wide search) — this is deferral item 1 from §2,
untouched since spec time.

- Install Tesseract (system binary, `winget`) + add `pytesseract` (and `Pillow` as a
  direct dependency — currently only transitive) to `backend/pyproject.toml`.
- New `ingestion/ocr.py`: render PDF page images (`pypdfium2`, already a transitive
  dep via `pdfplumber`) → `pytesseract` → text.
- Wire into `pipeline.py`'s `needs_ocr` branch: run OCR instead of stopping, tag
  `extraction_method=ocr`, continue to `decompose`. Missing-binary case still fails
  loudly and recoverably (SPEC §10) — readable error, not a crash.
- **AC:** a synthetic scanned-style fixture reaches `decomposed`/`stored` via OCR,
  `document.extraction_method=ocr` visible; Tesseract-missing case produces a
  structured error, not an unhandled exception.

### CHECKPOINT C11 — Phase 11 CLOSED 2026-07-30

All three tasks demoed live against the real running system. T11.1: browser
reload mid-conversation, history re-rendered, no dupes. T11.2 + T11.3: the
Browser pane went into a non-displayed state mid-session (clicks stopped
landing though DOM/network still worked) — substituted curl against the same
live backend/Postgres/agent subprocess, which is at least as strong a proof
for backend-only capability/pipeline changes. T11.2: three live
create→approve→persist cycles (Job+Application+ApplicationEvent+audit row
each), one live update-via-returned-application_id cycle (status changed in
place, event appended, zero duplicate rows), plus an incidental proof that
approval expiry still blocks the write. T11.3: a real synthetic scanned PDF
(rasterized text, no text layer) uploaded through the REST endpoint reached
`stored` with `extraction_method=ocr` and correctly decomposed credentials.

Unplanned P0 found during T11.1 verification: the SDK's built-in tools
(Bash/Read/Write/Edit) were reachable with zero approval — fixed with
`tools=[]`, regression-tested (confirmed RED before GREEN). See devlog.

Quality gates at close: 63 backend tests (up from 51) + ruff + mypy strict +
frontend tsc, all clean. Commits: `1b5add5` (security), `98e417e` (T11.1),
`8fc04b7` (T11.2), `0151bbf` (T11.3) — all on branch `v1.5`.

Per the user's explicit sequencing: pause here and reconsider scope before
any "big upgrade" work.

---

## 15. Phase 12 amendment — v2: job capture + profile layer

Opened 2026-07-30, after Phase 11 close (`b963639`) and the user's explicit pause to
reconsider scope. Confirmed via `interview-me` (full interview record in
`docs/intent/v2-job-capture-and-profile.md`). Same rules as §2/§14 carry over
unchanged: pinned budget, binding order, >25% overrun defers the next item, no box
extension.

**Budget: ~8h**, new pinned number on top of v1's ~13h10 + Phase 11's ~3h.

**Why:** long-term vision is job hunting + individualized services + mental care
combined. Too large to build directly. This phase grounds the platform in one real
job-hunting slice (job capture + real matching) *and* lays the first architectural
groundwork for the bigger vision (a generic personalization data layer) — deliberately
a baseline of each, not the full vision of either.

**Deliberate scope cuts (decided during the interview, not oversights):**
- No automated job-data fetching of any kind — not Google-result scraping, not
  LinkedIn, not even ATS JSON-endpoint polling (Greenhouse/Lever-style). Manual paste
  only. Ruled out (not deferred) once weighed against building a real product: ToS/
  enforcement risk scales with commercial use in a way "slow and polite" fetching
  doesn't fix, and a posting the user personally found is a better freshness/
  authenticity signal than anything a scraper could infer — this was the original
  motivating problem, and manual paste solves it by construction.
- `job_search_match`'s stub docstring names pgvector similarity as its promotion path
  (deferral item 4, still open). This phase promotes it with **direct LLM comparison
  of stored `Job`/`Credential` text**, not vector similarity — pgvector population
  stays deferred.
- No domain/subagent restructuring (the "how the agent is structured" half of the
  architecture question). One concession: `ProfileFact` is a generic key/value model,
  not job-seeking-specific, so a future domain can read the same table without a
  migration.
- No resume/JD tailoring, no mental-care features, no auth/multi-candidate, no wiring
  `job_search_match` to actually read the profile layer yet (exists + round-trips;
  consulted by matching is the next increment).

| # | Task | Box | Cumulative |
|---|------|-----|-----------|
| 12.1 | `ProfileFact` schema + repository (Protocol + Postgres + memory + conformance) | 60m | 1:00 |
| 12.2 | Profile capabilities: `profile_save` (write, gated) + `profile_recall` (read) | 60m | 2:00 |
| 12.3 | Job-posting extraction module (`ingestion/job_extract.py`) | 60m | 3:00 |
| 12.4 | `job_capture` capability: paste → extract → store behind one approval | 50m | 3:50 |
| 12.5 | `JobRepository.list_for()` — Postgres + memory + conformance update | 30m | 4:20 |
| 12.6 | `job_search_match` promotion: real fit assessment vs. stored jobs + credentials | 70m | 5:30 |
| 12.7 | Tests + quality gates (unit/integration, golden-set update, ruff/mypy/pytest) | 70m | 6:40 |

~1h20 headroom against the 8h ceiling — intentionally larger than v1's phases usually
carried, because this phase touches more genuinely novel surface (first LLM extraction
for a new domain, first generic cross-domain schema) than a promotion-ladder task did.

### T12.1 — `ProfileFact` schema + repository (60m)

New table: `candidate_id` (FK), `key` (str), `value` (text/JSONB), `updated_at`.
Generic by design — not `job_preference`, just `profile_fact` — so it's reusable by a
future mental-care domain without a migration. `set()` is an upsert on
`(candidate_id, key)`; `get_all()` returns everything for a candidate. Protocol in
`repositories/base.py`, Postgres + memory impls, under the existing conformance suite.
- **AC:** conformance suite passes for both implementations; upsert semantics verified
  (setting the same key twice updates, doesn't duplicate).

### T12.2 — Profile capabilities (60m)

`profile_save` (write: one or more key/value facts in one call, mirrors
`resume_store`'s batched-approval shape) + `profile_recall` (read-only, no gate).
`CapabilityContext` gets a `profile: ProfileRepository` field, wired in `main.py`.
Intent builder registered in `registry.py`'s `_WRITE_INTENTS`
(`f"mcp__{SERVER_NAME}__profile_save"`), descriptive per §11
("Save that you prefer remote roles in fintech to your profile?").
- **AC:** "Remember that I prefer remote roles in fintech" → one descriptive approval
  → fact persisted; a later turn asking "what do you know about my job preferences?"
  correctly recalls it via `profile_recall`, no approval needed for the read.

### T12.3 — Job-posting extraction module (60m)

`ingestion/job_extract.py`, mirrors `ingestion/decompose.py`'s shape: pasted job text
in, Pydantic-validated structured data out (`JobIn` fields + a `raw` dict for
requirements/highlights extracted but not in the typed schema). Malformed/non-job-like
input raises a typed error (mirrors `DecompositionError`), handled gracefully by the
capability, not a crash.
- **AC:** a real job posting's pasted text extracts into correct `title`/`company` +
  a populated `raw` dict; garbage input produces a readable "couldn't extract" message,
  not an exception.

### T12.4 — `job_capture` capability (50m)

New tool, same shape as `resume_store`: pasted job text → T12.3 extraction →
`ctx.jobs.add()` behind one batched approval. Intent builder added to
`_WRITE_INTENTS` (e.g. "Save this posting — {title} at {company} — so you can check
your fit against it?").
- **AC:** paste a real job posting into chat → one approval → structured `Job` row
  persisted (`source="user_pasted"` or similar, distinct from
  `application_track`'s `"user_reported"`).

### T12.5 — `JobRepository.list_for()` (30m)

Current Protocol only has `add()`. `job_search_match` needs to read back captured
jobs. `Job` has no `candidate_id` column today (`application_track` doesn't scope it
either) — add `list_for(candidate_id)` that joins through `Application` where one
exists, or falls back to "all `Job` rows" given v1/v2's single-candidate constraint;
exact join shape decided at implementation time, not here. Both impls + conformance
update.
- **AC:** jobs captured via T12.4 (no `Application` yet) and jobs created via
  `application_track` both come back from one query.

### T12.6 — `job_search_match` promotion (70m)

Rewrite the stub body only (per the promotion invariant — no registry/routing/
frontend changes). New optional `job_id` arg (mirrors `application_track`'s
`application_id` pattern): if given, assess fit between that specific `Job` and the
candidate's stored credentials via a real LLM call grounded in both; if omitted, fall
back to the existing general-guidance behavior (preserves the "what should I look
for" use case). No pgvector — direct text comparison, per the scope cut above.
- **AC:** after capturing a real posting (T12.4), asking "how do I match this job?"
  returns an assessment that references actual stored credential content and actual
  job content — not a generic answer indistinguishable from the old stub.

### T12.7 — Tests + quality gates (70m)

Unit tests for `ProfileFact` repo (upsert), extraction error paths, both new
capabilities' approval-gated writes, `job_search_match`'s two arg modes. Update the
routing eval golden set with cases for `profile_save`/`profile_recall`/`job_capture`
triggers (new tools change routing surface — same reason T7.2's golden set exists).
`ruff check`, `ruff format --check`, `mypy app`, `pytest`, frontend `tsc` all clean —
no frontend changes expected, but the check still runs.
- **AC:** all quality gates green; golden set still clears the ≥80% gate.

### CHECKPOINT C12 — Phase 12 CLOSED 2026-07-30

Both flows demoed live against the real running system (backend + Postgres +
agent subprocess), via SSE + curl against the same live server the browser
frontend was serving from.

**Flow 1 — job capture → real match.** Pasted a job posting into chat →
`job_capture` routed → one descriptive approval ("Save the job posting you
shared (~25 words) so you can check your fit against it?") → approved →
`Job` row persisted with `source=user_pasted` and a populated `raw` dict
(requirements/location correctly extracted), audit row present. Follow-up
turn referencing the returned `job_id` → `job_search_match` returned an
assessment citing actual stored credentials by name (pgvector/Postgres work,
a 2M-events/day service, real date ranges), computed tenure against the
posting's "5+ years" bar, and correctly flagged a skill as thin because no
bullet backed it — not a generic stub answer.

**Flow 2 — profile round-trip.** "Remember for later: remote only, fintech
or dev tools, 165k minimum" → `profile_save` → descriptive approval listing
the facts in plain language → approved → 3 `profile_fact` rows in Postgres.
Then, in a **fresh conversation**, "What do you know about my job
preferences?" → `profile_recall` returned all three correctly, with no
approval prompt (read-only path). The fresh conversation is the point: this
proves durable storage, not conversation memory.

Incidental proof during Flow 2's first attempt: the 90s approval timeout
fired before the decision was posted, the write did not happen, and the
agent degraded gracefully ("saving timed out on approval — want me to try
again?"). The gate still holds.

**Routing eval:** 89% (17/19), above the ≥80% gate, ~$0.11/run. First run
surfaced a real regression — `profile_recall`'s tool description was
permissive enough to hijack routing from `strategy_convo` and
`application_track`; tightened and re-verified. The remaining 2 failures on
the re-run were a different, unrelated pair (`application_track` cases that
passed in run 1) — normal run-to-run LLM sampling variance, not a code
issue.

**Quality gates at close:** 79 backend tests (72 unit + 7 integration, up
from 63) + ruff check/format clean on every file touched this phase +
frontend `tsc` and `vite build` clean.

Two known gaps, both pre-existing and unrelated to this phase's diff:
`mypy` could not be run at all (a Windows Application Control policy blocks
`.venv/Scripts/mypy.exe` — confirmed via Bash, PowerShell, and
sandbox-disabled; user opted to proceed and fix the policy separately), and
`ruff format --check .` fails repo-wide on ~10 files this phase never
touched (a ruff version bump since Phase 11 closed).
