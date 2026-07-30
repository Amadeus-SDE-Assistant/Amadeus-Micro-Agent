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
- [x] /impeccable init → PRODUCT.md (named-character brand, WCAG AA floor)
- [x] /impeccable polish on chat + upload + approval surfaces — actual ~55m,
      verified desktop + mobile with full chat→approval→stored path

## Phase 10 — Ship docs (90m)
- [x] README verified-by-clean-run (every command executed this build)
- [x] ADR-0001 stack, ADR-0002 approval design (incl. the allowed_tools trap)
- [x] Fine-tuning proposal — verdict: not yet; 4 numbered reopen-triggers
- [x] Deployment plan + Dockerfile sketch (bundled-CLI + Proactor findings)
- [x] CHECKPOINT C10: final commit — **v1 closed 2026-07-30**, actual ~70m

---

## Phase 11 — Gap-closing pass (~3h, SPEC §14)
- [x] T11.0 (unplanned, P0): SDK built-in tools (Bash/Read/Write/Edit) were
      reachable with zero approval — found live while verifying T11.1. Fixed
      with `tools=[]`; regression test confirmed RED before GREEN. Commit `1b5add5`.
- [x] T11.1 Chat history re-render: GET route + client persistence + hydrate (35m)
      — verified live (reload mid-conversation, no dupes). Commit `98e417e`.
- [x] T11.2 `application_track` promotion: Job + Application repos, context wiring,
      capability rewrite, intent builder — no-dedup design approved 2026-07-30 (70m).
      Verified live via curl against the real server + real Postgres: create -> one
      approval -> Job+Application+ApplicationEvent+audit row persisted (3x); update
      via returned application_id -> status changes in place, event appended, zero
      duplicate Job/Application rows; expiry still blocks writes.
- [x] T11.3 OCR fallback: Tesseract install (winget, UB-Mannheim build), ocr.py
      (pdfplumber rasterize + pytesseract, explicit install-path fallback since
      PATH isn't reliable for winget on Windows), pipeline.py needs_ocr branch
      now runs OCR instead of stopping; missing-binary path fails to
      status=failed with a reason, not a crash (65m). Verified live: uploaded
      a synthetic scanned PDF (rasterized text, no real text layer) through
      the real REST endpoint -> status=stored, extraction_method=ocr, 2
      credentials correctly decomposed from the OCR'd text.
- [x] CHECKPOINT C11: T11.1 demoed live in-browser (reload mid-conversation).
      T11.2 + T11.3 demoed live via curl + direct Postgres inspection against
      the real running server, DB, and agent subprocess — the Browser pane
      went into a non-displayed state mid-session (clicks stopped landing;
      DOM/network still worked), so curl substituted for click-testing from
      T11.2 onward. All quality gates clean at close: 63 backend tests +
      ruff + mypy + frontend tsc. Phase 11 CLOSED 2026-07-30.

---

## Deferral list — FINAL STATE at v1 close
1. OCR fallback — **deferred** (needs_ocr path stops cleanly; trigger = first real
   scanned resume; install = winget tesseract + pytesseract)
2. UI pass — **NOT deferred**: shipped in P9 (impeccable, ~55m)
3. emotional_support + job_search_match stubs — **NOT deferred**: all 5 shipped in P6
4. pgvector population — **deferred by design** (columns exist, unpopulated;
   trigger = job_search_match promotion)
5. Postgres → SQLite — **never triggered** (Docker green all build)

Only 2 of 5 pressure valves were used, both by design rather than schedule pressure.

## Final time accounting (pinned budget ~14h)
| Phase | Box | Actual |
|---|---|---|
| 0–2 spec/plan/preflight | 1h20 | ~1h35 |
| 3 walking skeleton | 2h00 | ~2h15 |
| 4 persistence | 1h30 | ~1h20 |
| 5 ingestion | 2h30 | ~1h55 |
| 6 capabilities+approval | 1h30 | ~1h40 |
| 7 evals+tests | 1h15 | ~1h05 |
| 8 review | 1h00 | ~1h10 |
| 9 UI pass | 1h00 | ~1h00 (incl. hook findings) |
| 10 ship docs | 1h30 | ~1h10 |
| **Total** | **~13h35** | **~13h10 — under the pinned ~14h** |
