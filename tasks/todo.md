# Task Checklist — Amadeus Micro Agent

Working checklist mirroring [plan.md](plan.md). Check items off as they land; record
actual time vs. box at each checkpoint. Deferral list state lives at the bottom.

## Phase 3 — Walking skeleton (120m)
- [x] T3.1 Backend scaffold: FastAPI, config, JSON logging, /api/health (30m)
- [x] T3.2 AgentService + registry + strategy_convo stub + error envelope (45m)
- [x] T3.3 SSE chat endpoint POST /api/chat (20m)
- [x] T3.4 React shell: ChatWindow, sse.ts, proxy (25m)
- [x] CHECKPOINT C3: demo, commit, pointer update — actual: ~135m (+12% over box;
      under the 25% escalation threshold, no deferral. Overrun causes: Windows
      event-loop discovery, SSE CRLF parser bug, StrictMode purity bug — all
      found by the live browser demo, which is the point of the checkpoint.)

## Phase 4 — Persistence (90m)
- [x] T4.1 docker-compose + DB wiring + truthful health (15m)
- [x] T4.2 SQLAlchemy models + initial Alembic migration (40m)
- [x] T4.3 Repository protocols + pg impls + fakes + chat persistence (35m)
- [x] CHECKPOINT C4: commit, pointer update — actual: ~80m (under box.
      Port 5432 collision with unrelated karyio-postgres container →
      Amadeus DB lives on host port 5433.)

## Phase 5 — Document ingestion (150m)
- [x] T5.1 Upload endpoint: validate, dedupe, BlobStore, document row (40m)
- [x] T5.2 pdfplumber extraction + scan detection → needs_ocr (30m)
- [x] T5.3 LLM decomposition → typed credentials, atomic, status transitions (50m)
- [x] T5.4 Upload UI + status display (30m)
- [x] CHECKPOINT C5: commit, pointer update — actual: ~115m (under box).
      Verified live in browser: upload → stored, 5 typed credentials; scanned
      PDF → clean needs_ocr stop. KNOWN ISSUE → P7: integration tests pollute
      the dev DB with fixture rows; needs a dedicated amadeus_test database.

## Phase 6 — Capabilities + approval gate (90m)
- [x] T6.1 ApprovalGate: can_use_tool, intent string, SSE event, audit rows (40m)
- [x] T6.2 resume_store real: pipeline + repo behind one batched approval (30m)
- [x] T6.3 Remaining 3 stubs + prompts.py (20m)
- [x] CHECKPOINT C6: definition-of-done demo, commit, pointer update — actual:
      ~100m (+11%, under threshold). SECURITY FIX from the live demo:
      allowed_tools bypasses can_use_tool — first demo wrote WITHOUT approval;
      write tools now excluded from allowed_tools + regression test. Approve
      and deny paths both verified live with audit rows.

## Phase 7 — Evals + tests (75m)
- [x] T7.1 Unit + integration suites per SPEC §9 (35m) — incl. dedicated
      amadeus_test DB; dev-DB pollution purged (P5 known issue closed)
- [x] T7.2 Routing eval harness, golden set, ≥80% (40m) — 94% (15/16) first
      run, $0.22, 122s; the one miss was a mislabeled golden case
- [x] CHECKPOINT C7: commit, pointer update — actual: ~65m (under box)

## Phase 8 — Review (60m)
- [x] /code-review since ec59c70; fix or waive findings — 10 fixed, 7 waived
      with reasons (docs/review/P8-review-notes.md); actual ~70m (+17%)
- [x] Manual reliability checks: API outage PASS, subprocess kill PASS —
      recorded in review notes

## Phase 9 — UI pass (60m)
- [ ] /impeccable init → PRODUCT.md
- [ ] /impeccable polish on chat + upload + approval surfaces

## Phase 10 — Ship docs (90m)
- [ ] README verified-by-clean-run
- [ ] ADR-0001 stack, ADR-0002 approval design
- [ ] Fine-tuning proposal (expected: "not yet" + triggers)
- [ ] Deployment plan + Dockerfile sketch
- [ ] CHECKPOINT C10: final commit — v1 closed

---

## Deferral list state (SPEC §2 — order binds)
1. OCR fallback — **deferred by default** (Tesseract not installed; trigger = first real scanned resume)
2. UI pass (phase 9) — active
3. emotional_support + job_search_match stubs — active
4. pgvector population — **deferred by design** (columns exist, unpopulated)
5. Postgres → SQLite — not triggered (preflight green)
