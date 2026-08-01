# Implementation Plan — Amadeus Micro Agent

Derived from [SPEC.md](../SPEC.md) (`ec59c70`). Phases and boxes come from SPEC §2; this
document decomposes them into implementable tasks with acceptance criteria.

Budget check: task boxes below sum to **~12.25h**; with the ~1h05m already spent on
phases 0–1, total lands at ~13.3h against the pinned ~14h. Buffer: ~40m.

**Rules carried from SPEC §2 (binding):**
- Any phase >25% over its box → defer the next deferral-list item immediately.
- Checkpoint ritual at every phase boundary: demo the exit criterion, commit,
  update the progress memory pointer.

---

## Dependency graph

```
P3 walking skeleton ──► P4 persistence ──► P5 ingestion ──► P6 capabilities+approval
                                                                    │
                                              P7 evals+tests ◄──────┘
                                                    │
                                              P8 review ──► P9 UI pass ──► P10 ship docs
```

- P4 depends on P3 (chat path exists to persist into).
- P5 depends on P4 (document/credential tables + BlobStore).
- P6 depends on P5 (resume_store wraps the ingestion pipeline) and P3 (agent loop).
- P7 depends on P6 (all five capabilities registered — routing evals need the full roster).
- P9 runs after P8 so the UI pass polishes reviewed, stable surfaces.
- Within phases, tasks are ordered; no cross-phase parallelism is planned (solo project).

Each phase is a **vertical slice**: it ends with a user-visible capability, not a layer.

---

## Phase 3 — Walking skeleton (box 120m)

Exit criterion: browser → type message → streamed agent reply that had a capability
tool available. Ugly is fine; alive is mandatory.

### T3.1 Backend scaffold (30m)
FastAPI app package per SPEC §7: `backend/pyproject.toml` (uv), `app/main.py`,
`app/config.py` (pydantic-settings), structured JSON logging with `request_id`,
`GET /api/health` (static OK for now), ruff + mypy config.
- **AC:** `uv run fastapi dev app/main.py` serves; `/api/health` returns JSON; every
  request logs one structured line; `ruff check` and `mypy app` pass.
- **Verify:** curl + log inspection.

### T3.2 AgentService + registry with one stub (45m)
`app/agent/service.py` wrapping `ClaudeSDKClient` (session per conversation, timeout on
every call, error envelope — SPEC §10 reliability rows 1–2). `app/capabilities/registry.py`
via `create_sdk_mcp_server` with **one** stub (`strategy_convo`) following the SPEC §4
stub contract, `# STUB:` marker included.
- **AC:** script-level round-trip returns streamed text; agent can invoke the stub tool
  (`mcp__jobseeker__strategy_convo` in `allowed_tools`); killing network/API mid-call
  yields a structured error object, not an exception escape or hang.
- **Verify:** small driver script + a forced-failure run.

### T3.3 SSE chat endpoint (20m)
`POST /api/chat` streaming agent messages as SSE events; error envelope as an SSE event
type, never a dropped connection.
- **AC:** `curl -N` shows streamed events for a prompt; a forced agent error arrives as
  an `error` event with readable message.
- **Verify:** curl transcript.

### T3.4 React shell (25m)
Vite + TS scaffold per SPEC §7: `ChatWindow`, `MessageList`, `lib/sse.ts`, dev proxy
`/api → :8000`. No styling (UI pass is P9).
- **AC:** browser chat round-trip works; `npm run typecheck` and `npm run build` pass.
- **Verify:** manual browser demo.

### CHECKPOINT C3
Demo exit criterion → commit → update progress pointer. **This is definition-of-done
item 1+5 in embryo; if it slips >30m, deferral rule fires.**

---

## Phase 4 — Persistence (box 90m)

Exit criterion: chat turns persist across backend restarts; schema matches SPEC §5.

### T4.1 Compose + DB wiring (15m)
`docker-compose.yml` (`pgvector/pgvector:pg16`, volume, healthcheck), async SQLAlchemy
engine in config, `/api/health` now reports real DB reachability (SPEC §10 observability).
- **AC:** `docker compose up -d db` + health endpoint reflects DB up/down truthfully.

### T4.2 Models + migration (40m)
SQLAlchemy models for all SPEC §5 tables; single initial Alembic migration; vector
columns present-but-unpopulated (deferral item 4); `CREATE EXTENSION vector` in migration.
- **AC:** `alembic upgrade head` on a fresh DB creates every table; `alembic downgrade
  base` is clean; JSONB and vector column types verified via psql.

### T4.3 Repositories + chat persistence (35m)
`repositories/base.py` Protocols (`CredentialRepository`, `DocumentRepository`,
`ConversationRepository`, `BlobStore`), Postgres implementations, in-memory fakes for
tests, chat path writes `conversation`/`message` rows keyed to `sdk_session_id`.
- **AC:** conformance test suite runs identically against fake and Postgres impls
  (pg via integration marker); restart backend mid-conversation → history rows survive.

### CHECKPOINT C4 — commit, pointer update.

---

## Phase 5 — Document ingestion (box 150m)

Exit criterion: upload a real PDF from the browser → typed credentials proposed.
**Highest-risk phase; deferral item 1 (OCR) is its pressure valve.**

### T5.1 Upload endpoint + validation + blob (40m)
`POST /api/documents`: MIME + size ≤10 MB + magic-bytes validation, sha256 dedupe
(reliability row 4), `BlobStore` write under `./data/blobs/`, `document` row with
`status=uploaded`.
- **AC:** valid PDF → 201 + blob on disk + row; same file again → dedupe response, no
  second blob; oversized/wrong-type/corrupt → 422 with reason; all transitions logged.

### T5.2 Text extraction + scan detection (30m)
`ingestion/extract.py` via pdfplumber; near-zero text → `status=needs_ocr` (OCR itself
deferred), else `extraction_method=text_layer`, `status=extracted`.
- **AC:** text-layer fixture → extracted text; synthetic image-only fixture →
  `needs_ocr`, pipeline stops cleanly, user-visible message says so.

### T5.3 LLM decomposition (50m)
`ingestion/decompose.py`: extracted text → typed credentials (Pydantic-validated LLM
structured output; `kind` ∈ SPEC §5 enum). Status transitions
`extracted → decomposed → stored` / `failed` + reason (reliability row 5). Atomic commit.
- **AC:** fixture resume yields plausible typed credentials that validate; malformed
  LLM output → `failed` with reason, zero partial rows; <60s budget logged (SPEC §10).

### T5.4 Upload UI (30m)
File-input + upload progress + ingestion status surfaced in the chat page.
- **AC:** browser: choose PDF → watch status reach `decomposed`; error states readable.

### CHECKPOINT C5 — commit, pointer update. **Synthetic fixtures only (SPEC §11 never-rule).**

---

## Phase 6 — Capabilities + approval gate (box 90m)

Exit criterion: "save my resume" in chat → one descriptive approval → credentials in
Postgres → audit row.

### T6.1 ApprovalGate (40m)
`agent/approvals.py`: `can_use_tool` hook intercepts write-capability calls → pending
approval with required **`intent: str`** (SPEC §11 descriptive-approval design) → SSE
`approval_request` event → `POST /api/approvals/{id}` resolves → agent resumes or
cancels. Every decision → `approval` audit row.
- **AC:** write call pauses the agent; approve → proceeds; deny → capability returns
  a polite cancellation; UI shows intent sentence, payload only on expand; audit row
  present for both outcomes.

### T6.2 resume_store real (30m)
Wire capability → ingestion pipeline + `CredentialRepository`, one batched approval for
the whole write set (SPEC §11 batch-granularity rule).
- **AC:** end-to-end chat flow stores credentials after exactly one approval; audit
  trail lists the batch; re-running is dedupe-safe.

### T6.3 Remaining stubs (20m)
`application_track`, `job_search_match`, `emotional_support` per stub contract;
`prompts.py` holds per-capability system prompts.
- **AC:** registry exposes 5 tools; each responds in chat; every stub carries `# STUB:`
  + promotion path docstring.

### CHECKPOINT C6 — **this is the SPEC definition-of-done demo.** Commit, pointer update.

---

## Phase 7 — Evals + tests (box 75m)

### T7.1 Test fill-in to SPEC §9 (35m)
Unit: stub contract shape, decomposition validation, repo conformance, ingestion
validation matrix. Integration: routes via `httpx.ASGITransport`, pg repos, SSE shape,
DB-down → 503 (reliability row 3).
- **AC:** `uv run pytest` green locally; integration suite green with compose DB up.

### T7.2 Routing eval harness (40m)
`tests/evals/`: golden set ~15 utterances → expected capability (SPEC §9 table seeds it),
`-m eval` marker, scored report, threshold ≥80%.
- **AC:** eval run prints per-utterance results + aggregate ≥0.80; excluded from default
  pytest; run cost logged.

### CHECKPOINT C7 — commit, pointer update.

---

## Phase 8 — Review (box 60m)

`/code-review` over everything since `ec59c70`; fix material findings; run the two
manual reliability verifications (API outage, SDK subprocess kill — SPEC §10) and record
outcomes in review notes.
- **AC:** review findings addressed or explicitly waived with reason; both manual checks
  documented.

## Phase 9 — UI pass (box 60m)

`/impeccable` over chat, upload, and approval surfaces. Functional behavior frozen —
visual/UX only. (First run: `/impeccable init` → PRODUCT.md, which also silences the
SessionStart hook nag.)
- **AC:** before/after screenshots; no functional diffs outside styling/markup.

## Phase 10 — Ship docs (box 90m)

README (run instructions = SPEC §6 verified against reality), `docs/adr/0001-stack.md`,
`docs/adr/0002-approval-design.md`, `docs/fine-tuning-proposal.md` (expected conclusion:
"not yet — trigger conditions listed"), `docs/deployment-plan.md` (SPEC §3 table +
Dockerfile sketch).
- **AC:** a stranger could clone and run from README alone; every SPEC §13 checkbox
  ticked; deferral list final state recorded.

### CHECKPOINT C10 — final commit; project v1 closed.

---

## Phase 11 — Gap-closing pass (box ~3h, SPEC §14)

Opened after v1 close and merge to `main`. Three honest gaps from
docs/v1-summary.md, closed as one small pinned increment before any "big upgrade."
`emotional_support` was considered and dropped — it already shipped in Phase 6.

### T11.1 Chat history re-render (35m)
`GET /api/conversations/{id}/messages` route + `MessageOut` response (repository
methods already exist on both implementations); client-side `conversationId`
persistence + fetch-on-mount hydration in `ChatWindow.tsx`.
- **AC:** reload mid-conversation → prior messages re-render in order, no duplicate
  send; zero-message conversation still mounts cleanly.

### T11.2 `application_track` promotion (70m)
`JobRepository` + `ApplicationRepository` Protocols + Postgres/in-memory impls
(neither exists yet); `CapabilityContext` gains `jobs`/`applications`; capability
body rewritten per the resume_store pattern; intent builder registered in
`registry.py`. **Design (approved):** no job dedup — always create a new `Job`
unless the agent passes back a known `application_id`; real matching is
`job_search_match`'s job, not this task's.
- **AC:** "I applied to X for role Y" → one approval → Job + Application +
  ApplicationEvent persisted, audit row present; a follow-up turn with the returned
  `application_id` appends an event instead of creating a duplicate Job/Application.

### T11.3 OCR fallback (65m)
Tesseract system binary (winget) + `pytesseract`/`Pillow` deps; new
`ingestion/ocr.py`; wired into `pipeline.py`'s `needs_ocr` branch in place of the
clean stop.
- **AC:** synthetic scanned fixture reaches `stored` via OCR,
  `extraction_method=ocr` visible; missing-binary case fails loudly (structured
  error), not a crash.

### CHECKPOINT C11
Demo all three live → commit → update progress pointer. Pause for scope
reconsideration before any "big upgrade" work.

---

## Phase 12 — v2: job capture + profile layer (box ~8h, SPEC §15)

Opened after Phase 11's pause and an `interview-me` session to scope v2
(`docs/intent/v2-job-capture-and-profile.md`). Two additions: a chat-native
job-capture capability (real `job_search_match` promotion) and a generic
personal-profile data layer — the first architectural groundwork for the
longer-term job-hunting + individualized-services + mental-care vision. No
automated job-data scraping/fetching (manual paste only — a deliberate legal/
product decision, not a shortcut); no pgvector; no domain/subagent
restructuring; no resume/JD tailoring, mental-care features, or auth.

### T12.1 `ProfileFact` schema + repository (60m)
New table (`candidate_id`, `key`, `value`, `updated_at`), generic/domain-agnostic
by design. Protocol in `repositories/base.py`, Postgres + memory impls under
the existing conformance suite. `set()` upserts on `(candidate_id, key)`.
- **AC:** conformance suite passes both impls; re-setting a key updates in
  place, doesn't duplicate.

### T12.2 Profile capabilities (60m)
`profile_save` (write, batched-approval shape like `resume_store`) +
`profile_recall` (read-only). `CapabilityContext` gains `profile`; intent
builder registered in `registry.py`.
- **AC:** "remember X" → one approval → persisted; later turn asking about it
  → `profile_recall` returns it correctly, no approval needed.

### T12.3 Job-posting extraction module (60m)
`ingestion/job_extract.py`, mirrors `ingestion/decompose.py`: pasted job text
→ Pydantic-validated `JobIn` + `raw` dict. Typed error on malformed input.
- **AC:** real posting text → correct title/company + populated raw dict;
  garbage input → readable error, not a crash.

### T12.4 `job_capture` capability (50m)
Pasted job text → T12.3 extraction → `ctx.jobs.add()` behind one approval.
Intent builder added.
- **AC:** paste a real posting → one approval → structured `Job` row
  persisted.

### T12.5 `JobRepository.list_for()` (30m)
Protocol currently only has `add()`. Add a read method covering jobs from
both `job_capture` and `application_track` origins. Both impls + conformance
update.
- **AC:** jobs from both capture paths return from one query.

### T12.6 `job_search_match` promotion (70m)
Rewrite stub body only. New optional `job_id` arg (mirrors
`application_track`'s `application_id`): given → real LLM-grounded fit
assessment against that job + stored credentials; omitted → existing
general-guidance behavior preserved. Direct text comparison, no pgvector.
- **AC:** after capturing a real posting, "how do I match this job?" returns
  an assessment grounded in actual stored data, not a generic answer.

### T12.7 Tests + quality gates (70m)
Unit coverage for the new repo/capabilities/extraction error paths; routing
eval golden-set additions for the two new tools; ruff/mypy/pytest/tsc clean.
- **AC:** all quality gates green; golden set still clears ≥80%.

### CHECKPOINT C12
Demo both flows live (capture→match, profile round-trip) → commit → update
progress pointer.
