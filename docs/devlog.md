# Dev log

## 2026-07-29 → 07-30 — v1, spec to close in one build day (~13h10)

### Morning — process setup (phases 0–2)

- Repaired a broken plugin install before any project work (impeccable was registered
  but its cache directory didn't exist — copied from marketplace source).
- **Spec session.** Budget renegotiated openly from 8h → ~14h as requirements landed
  (PDF ingestion with OCR fallback, cloud-portability plan, reliability floor,
  descriptive approvals). Binding deferral list + escalation rule written into SPEC §2.
- **Preflight** retired every environment risk in 15 minutes: SDK end-to-end smoke
  ($0.036), pgvector image boot-tested, Docker Desktop found stopped (started it),
  `ANTHROPIC_API_KEY` unnecessary in dev (CLI login carries).
- **Plan:** 20 tasks, acceptance criteria each, vertical slices, checkpoint ritual
  (demo → commit → progress pointer).

### Midday — walking skeleton + persistence (phases 3–4)

- Skeleton live in browser at C3 after three landmines, all found by the live demo:
  1. `uvicorn --reload` installs the Selector loop on Windows → SDK subprocess spawn
     fails with `NotImplementedError`. Fix: `run.py` pins Proactor, no reload.
  2. SSE client split frames on `\n\n`; sse-starlette emits `\r\n\r\n`. curl hid it.
  3. React StrictMode crashed on an impure setState updater.
- First live capability turn: agent → `strategy_convo` → nested LLM call in-process,
  34s, $0.21. Architecture proven.
- Persistence came in under box. Port 5432 occupied by an unrelated project's
  Postgres → Amadeus lives on 5433. Alembic needs the *Selector* loop (asyncpg) while
  the app needs Proactor — both pinned, both documented.

### Afternoon — ingestion + approvals (phases 5–6)

- Full pipeline (validate → blob → pdfplumber → LLM decompose → store) verified in
  the browser: synthetic resume → 5 typed credentials on screen. Scanned-style PDF →
  clean `needs_ocr` stop, zero wasted LLM calls.
- Found integration tests polluting the dev DB → logged for P7.
- **The security catch of the project:** first approval demo wrote credentials with
  no prompt. `allowed_tools` *bypasses* `can_use_tool` entirely. Write tools now
  excluded from `allowed_tools` + regression test. All 46 unit tests had been green
  throughout — only the live demo caught it. (The SDK's own
  `CanUseToolShadowedWarning` later confirmed the semantics.)
- Approve and deny paths both verified live with audit rows; deny wrote nothing.

### Evening — evals, review, polish, ship (phases 7–10)

- Dedicated `amadeus_test` DB; dev-DB pollution purged.
- **Routing eval: 94% (15/16), $0.22, 122s.** The one "failure" was a mislabeled
  golden case — the agent correctly asked for resume content instead of calling a
  storage tool with nothing to store. First-eval lesson: you debug the eval too.
- Two-axis review (parallel sub-agents): 10 findings fixed (headliner: sha256 dedupe
  permanently blocked retrying a failed ingestion), 7 waived with recorded reasons.
  Manual reliability checks passed by actually breaking things: dead API endpoint →
  readable error, stream alive; killed `claude.exe` mid-turn → error event + fresh
  session with restart notice.
- UI pass: PRODUCT.md (named-character brand, WCAG AA floor), warm-paper Operate
  world, approval card as the signature consent moment. Design hook pushed Fraunces →
  **Libre Baskerville** (cut 1757; Mozart b. 1756 — period-correct for Amadeus).
- Ship docs: README (all commands verified by execution), 2 ADRs, fine-tuning
  proposal (verdict: not yet, 4 reopen triggers), deployment plan (bundled CLI
  simplifies the container; API key mandatory in prod).

**Close: 27 commits, ~13h10 vs ~14h pinned, 2 of 5 deferral valves used — both by
design, neither from schedule pressure.**
