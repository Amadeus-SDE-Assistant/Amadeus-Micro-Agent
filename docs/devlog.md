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

---

## 2026-07-30 — Phase 11, gap-closing (~3h)

Three honest gaps from the v1 summary, closed as one pinned increment before allowing
any "big upgrade" talk. `emotional_support` was considered and dropped — it already
shipped in Phase 6, so the task didn't exist.

- **A P0 fell out of unrelated verification.** While live-checking the chat-history
  reload, the agent ran real `Bash` and `Read` calls on a test message. `ClaudeAgentOptions`
  never set `tools=[]`, and `ApprovalGate`'s "no registered write-intent = read-only,
  allow" rule — written for four read-only stubs — silently extended that permission to
  every SDK built-in. Fixed with `tools=[]`; the regression test was confirmed RED
  against pre-fix code before being accepted as GREEN. **A permissive default is a
  vulnerability, not a convenience** — and the second security hole this project found
  by demoing rather than reading.
- `application_track` promoted: new `JobRepository` + `ApplicationRepository`, no dedup
  by design (real matching belongs to `job_search_match`, not here).
- OCR fallback: winget Tesseract + `pytesseract`. Windows quirk — winget's PATH
  registration doesn't reach already-running processes, so `ocr.py` carries an explicit
  install-path fallback. The fixture rasterizes real text via PIL, so the test proves
  actual OCR recovery rather than just the error path.
- Mid-phase the Browser pane went non-displayed — clicks stopped landing while DOM and
  network still worked. Substituted curl against the same live backend/DB/agent. For
  backend-only changes that's at least as strong a proof; worth knowing the fallback exists.

**Close: C11 demoed live, 63 tests (from 51).**

## 2026-07-30 — Phase 12, v2 (8h box)

Opened with an `interview-me` pass instead of picking from the roadmap list — the right
call, because what came out wasn't on it.

- **The stated goal turned out to be much larger than "v2":** job hunting +
  individualized services + mental care on one platform. Too big to build, so v2 became
  "ground it in one real job-hunting slice *and* lay one piece of architecture for the
  rest."
- **The interview's pivotal turn was a scope *reduction*.** The plan started as Google
  keyword scraping, moved to rate-limited "polite" fetching, then to ATS JSON endpoints
  — and then the user rejected all of it on product grounds: enforcement risk scales
  with commercial use in a way slow-and-polite doesn't fix. Manual paste sidesteps the
  legal question entirely *and* is a better freshness signal, since a posting you
  personally found beats anything a scraper infers. That was the original problem
  (stale/fake listings) solved by construction rather than by heuristics.
- **A live smoke test caught what unit tests couldn't.** T12.6's first pass formatted
  credentials as kind/title/org only, dropping `body.bullets`. Tests asserted the
  capability returned text; it did — text saying "no data" about skills that were
  sitting in the database. Only running it for real exposed it.
- **The eval caught a cross-capability regression.** `profile_recall`'s description
  ("…or when a saved preference would help answer their question") was permissive
  enough to hijack routing from two other capabilities. 89% (17/19), fixed and
  re-verified. Second time this project's eval earned its cost by finding something no
  test was looking for.
- **`mypy` looked blocked all session** — Windows Application Control, os error 4551.
  Seven commits shipped with a caveat attached before noticing that `pytest.exe` and
  `ruff.exe` ran fine from the same `.venv/Scripts/`. It was never a path rule; it
  blocks the `mypy.exe` shim, not the package. `python -m mypy app` works, and Phase 12
  typechecks clean. **Lesson: when a tool fails, check whether its neighbours do too
  before accepting the constraint.**
- Process miss: no wall-clock actual was recorded, breaking a ritual every prior phase
  kept. Boxes summed to 6h40 against the 8h pin; what it truly cost is unrecoverable.

**Close: C12 demoed live (capture→match, and a profile round-trip proven across a
*fresh* conversation — the point being durable storage, not chat memory). 79 tests,
8 capabilities, merged to `dev-v3` via PR #4.**
