# CLAUDE.md — Amadeus Micro Agent

Project instructions for Claude Code sessions in this repo. Read this first, every
session, before touching code.

## What this project is

Architecture-first job-seeking chatbot. The point is a capability container that
grows cleanly — not a finished feature set. v1 closed 2026-07-30 (~13h10 vs a ~14h
pinned budget); a small follow-up increment (Phase 11, ~3h) is scoped in SPEC.md §14.
Full context: [SPEC.md](SPEC.md) (source of truth), [PRODUCT.md](PRODUCT.md) (brand/UX
floor), [tasks/todo.md](tasks/todo.md) (working checklist), [docs/v1-summary.md](docs/v1-summary.md)
(gaps + roadmap), [docs/devlog.md](docs/devlog.md) (narrative history).

## Session start protocol

1. Read SPEC.md's most recent numbered section (amendments append, never rewrite
   history) and `tasks/todo.md` to find the current phase/task.
2. Check auto-memory (`amadeus-progress` and `amadeus-micro-agent-vision`) for the
   phase pointer and standing rules — but verify against `git log` and the actual
   files, since memory can go stale (it already has once this project).
3. Don't re-derive settled decisions (stack, schema, approval design) — they're in
   SPEC.md §3–§5 with rationale. Read before proposing alternatives.

## The process this project runs on (keep following it)

- **Pinned budgets, named in hours, per phase/task.** Any new scope gets priced
  against the remaining budget and stated numerically before starting — never
  absorbed silently. If a phase/task runs >25% over its box, defer the next item
  immediately; don't extend the box or renegotiate mid-phase.
- **Checkpoint ritual** at every phase boundary: demo the exit criterion live
  (browser, curl, or equivalent), commit, update the `amadeus-progress` memory
  pointer. A phase isn't done until it's been demonstrated working, not just
  written.
- **Vertical slices**, not layers. Each phase/task ends with something a user could
  observe, not an internal refactor.
- **SPEC amendments are additive.** When reality overrides a spec decision, add a
  dated amendment section/note — don't silently edit the original text out from
  under the historical record.
- **Approval prompts are descriptive, not literal.** Any write capability's
  approval text states intent in plain language ("save these 5 credentials to your
  profile?"), never a raw payload/diff dump. See SPEC.md §11.
- **Commit style:** task-prefixed, descriptive (`T4.2: …`, `C6: …`), not
  Conventional Commits — matches `tasks/plan.md` task IDs. Only commit when asked.

## Architecture invariants (don't break these without flagging it first)

- Promoting a capability stub to real must mean rewriting **one function body**.
  Never touch routing, the registry, the data layer, or the frontend to do it.
- Capabilities never import each other — all coordination goes through the agent
  loop.
- Repositories are `Protocol` classes; capabilities depend on the protocol, never a
  concrete implementation. New repositories get an in-memory fake under the same
  conformance-test suite as the Postgres implementation.
- Write tools must **never** appear in `allowed_tools` — that list bypasses
  `can_use_tool` entirely (the security lesson in ADR-0002). Every write goes
  through `ApprovalGate` + an intent builder in `registry.py`'s `_WRITE_INTENTS`.
- All agent file access stays inside `./data/`. No PDFs as DB rows — blobs go
  through `BlobStore`.

## Windows-specific landmines (already fixed once — don't reintroduce)

- Backend runs via `uv run python run.py`, **not** `uvicorn --reload` — the SDK
  subprocess needs the Proactor event loop; `--reload` installs the Selector loop
  and breaks subprocess spawn. See ADR-0001.
- Alembic migrations pin `WindowsSelectorEventLoopPolicy` (asyncpg) — deliberately
  different from the app runner's Proactor pin. Both are correct; don't "fix" one
  to match the other.
- SSE frames are CRLF-separated (`sse-starlette` default) — a client splitting on
  bare `\n\n` will silently misparse. curl hides this; test with the real frontend.
- React StrictMode requires pure `setState` updaters — impure updaters crash in dev
  only, not prod, which makes them easy to miss.

## Skill usage — be proactive, don't wait to be told

This session's default so far has been direct tool use (Bash/Read/Edit) even where a
skill existed for the job. Going forward, **reach for a matching skill rather than
freehanding it**, especially for anything process-shaped rather than a one-line fix.
Five plugin packages are installed (`installed_plugins.json`, confirmed 2026-07-30) —
every row below maps to one of them, so none go unused by default:

| Package | Installed | Role in this project |
|---|---|---|
| `agent-skills` (addy-agent-skills) | 2026-07-29 | Default SDLC skillset — spec, plan, build, test, review |
| `impeccable` | 2026-07-29 | UI/design pass — already ran once (Phase 9, PRODUCT.md) |
| `mattpocock-skills` (claude-plugins-official) | 2026-07-29 | TDD, diff-scoped two-axis review, debugging loop, domain/codebase design vocabulary |
| `understand-anything` | 2026-07-29 | Codebase/diff comprehension via knowledge graph — useful for a fresh session or a large diff, not routine edits |
| `figma` (claude-plugins-official) | 2026-07-17, predates this project | Only relevant if the UI gets formalized in/from a Figma file |

| Situation | Skill |
|---|---|
| Starting a new phase/feature, or amending SPEC.md | `agent-skills:spec` or `spec-driven-development` |
| Breaking a phase into tasks with acceptance criteria | `agent-skills:plan` or `planning-and-task-breakdown` |
| Implementing a task: build → test → verify → commit | `agent-skills:build` (add "auto" to run a whole approved plan) |
| Writing tests for new/changed logic, or a bug fix | `agent-skills:test` / `test-driven-development`, or `mattpocock-skills:tdd` for a strict red-green-refactor pass |
| Before merging / at a checkpoint's review step | **`mattpocock-skills:code-review`** — diff-scoped, two Standards+Spec sub-agents; this is the pattern Phase 8's C8 review already used. Prefer it over `agent-skills:review` for anything scoped to "since commit X"; use `agent-skills:review`/`code-review-and-quality` for a broader five-axis pass instead |
| A test fails / behavior doesn't match expectations and the cause isn't obvious | `mattpocock-skills:diagnosing-bugs` for the diagnosis loop, or `debugging-and-error-recovery` — pick one, don't run both |
| Anything touching upload validation, approval gate, auth-adjacent code | `security-and-hardening` or the `security-auditor` agent |
| Frontend/UI work — chat window, approval card, upload UI | `impeccable` (PRODUCT.md is the brand contract — respect it, don't relitigate) |
| Designing/changing a repository Protocol or a capability's interface (e.g. the T11.2 `JobRepository`/`ApplicationRepository` seam) | `mattpocock-skills:codebase-design` for the deep-module/seam vocabulary before writing the Protocol |
| Pinning down a term or enum before it spreads (e.g. `application` status values, `credential.kind`) | `mattpocock-skills:domain-modeling` |
| Sanity-checking a state model or UI shape before committing to it | `mattpocock-skills:prototype` (throwaway, answers one design question) |
| Researching an external library/API before depending on it (e.g. `pytesseract`/Tesseract for T11.3) | `mattpocock-skills:research` — captures findings as a repo markdown file instead of trusting recall |
| Stress-testing a decision already made, before it's load-bearing | `mattpocock-skills:grilling` |
| Recording a decision (schema change, new dependency, architecture deviation) | `documentation-and-adrs` |
| Onboarding a fresh session/collaborator, or auditing architecture at a glance | `understand-anything:understand` (full graph) or `understand-onboard` — reach for this before re-deriving structure by hand |
| Understanding a specific PR/diff's blast radius (e.g. reviewing PR #2, or a future PR) | `understand-anything:understand-diff` |
| Deep-diving one file/module you didn't write or haven't touched in a while | `understand-anything:understand-explain` |
| Pushing the shipped UI into Figma (portfolio/recruiter-facing artifact), or building a new screen from a Figma design | `figma:figma-generate-design` or `figma:figma-design-to-code` — not triggered by routine frontend work, only an explicit Figma ask |
| Verifying a UI change actually works in the browser | `run` skill, or the standard preview-tool verification workflow |
| Committing, branching, or resolving conflicts | `git-workflow-and-versioning`, or `mattpocock-skills:resolving-merge-conflicts` if a rebase/merge is actually mid-conflict |
| Adding structured logging/metrics for a new code path | `observability-and-instrumentation` |

**Overlap rule:** where `agent-skills` and `mattpocock-skills` both cover a situation
(TDD, code review, debugging), pick one per the notes above and don't run both —
that's ceremony inflation, not diligence, and this project's whole ethos is against
padding scope.

Don't invoke a skill reflexively for trivial edits (a one-line typo fix, a memory
file update, a doc correction) — match the ceremony to the size of the change, the
same discipline this project already applies to phase boxes.

## Commands (verified; see README.md for the full list)

```bash
docker compose up -d db                     # Postgres on host :5433
cd backend && uv sync && uv run alembic upgrade head && uv run python run.py   # :8000
cd frontend && npm install && npm run dev   # :5173, proxies /api → :8000

cd backend
uv run pytest                       # unit — fast, no tokens, no DB
uv run pytest -m integration        # needs the dedicated amadeus_test DB
uv run pytest tests/evals -m eval   # routing eval vs the real agent (~$0.25/run)
uv run ruff check . && uv run ruff format --check . && uv run mypy app
```

```bash
cd frontend && npm run typecheck && npm run build
```
