# v1 summary & roadmap

> **Superseded (2026-07-30):** the "Honest gaps" and "Future improvements" sections
> below are a snapshot at v1 close and are now partly stale — items 1, 2, 5, and 6
> shipped in Phases 11–12. See [v2-summary.md](v2-summary.md) for current state, a
> reconciliation table, and the live roadmap. The "What v1 is" section remains accurate
> as history.

Closed 2026-07-30 at checkpoint C10 (`58fd045`). ~13h10 actual against a ~14h pinned
budget, built spec-first in one continuous arc: spec → plan → skeleton → persistence →
ingestion → approvals → evals → review → UI → ship docs.

## What v1 is

One conversational surface for a job seeker, on an architecture built to grow:

| Delivered | Evidence |
|---|---|
| 5 capabilities behind an in-process MCP registry (1 real, 4 promotion-ready stubs) | `backend/app/capabilities/` — adding one = one file + one list entry |
| Human-approved writes with descriptive intents + full audit trail | ADR-0002; approve/deny/expire all verified live, audit rows conversation-linked |
| PDF resume ingestion → typed credentials | validate → blob → pdfplumber → LLM decompose (Pydantic-strict) → store; scanned PDFs stop cleanly at `needs_ocr` |
| Chat persistence (Postgres, full SPEC §5 schema, pgvector-ready) | conformance-tested repositories, memory ↔ Postgres symmetric |
| Reliability floor | timeouts everywhere, error envelope, subprocess-death recovery with restart notice — verified by killing the subprocess |
| Routing eval harness | **94%** on 16 golden utterances, ≥80% gate, ~$0.25/run — the regression net for stub promotion |
| Styled, WCAG-AA, named-character UI | warm-paper Operate world, Libre Baskerville wordmark, approval card as signature moment |
| Complete process record | SPEC (amendment-marked), plan with actuals, two-axis review + waivers, 2 ADRs, fine-tuning proposal, deployment plan, this log |

Quality gates at close: 51 unit + 4 integration tests, ruff + mypy strict + tsc clean.

## Honest gaps (recorded, not hidden)

- Chat history persists but does not re-render after page reload (SPEC §12 Q3).
- OCR deferred — scanned PDFs are detected and refused politely, not read.
- Stubs answer well but store nothing (by design; contracts stable).
- `dev` branch is local — nothing pushed.
- Approval works only while the originating stream is open; there is no
  reconnect-and-resume for approvals.

## Future improvements

**Near-term (hours each)**
1. Push `dev`, PR to `main`.
2. History re-render on reload: `GET /api/conversations/{id}/messages` + hydrate —
   the rows and repository method already exist.
3. `technical_qa` capability stub (user-requested post-C6): one file, one registry
   line, two golden-set cases.
4. Idle-session reaper in AgentService (bounds subprocess memory).

**Mid-term (the promotion ladder — each grows the eval golden set)**
5. Promote `application_track`: real writes to `application`/`application_event`
   behind the approval gate (schema already migrated). Easiest first promotion.
6. OCR fallback when the trigger fires (first real scanned resume): Tesseract +
   `pytesseract`, slot already marked in `ingestion/ocr` design.
7. Promote `job_search_match`: real job source + populate pgvector embeddings
   (columns waiting); similarity search joins relational filters in one query.
8. Resume/JD tailoring flow — highest direct user value on stored credentials.

**Longer-term**
9. Deploy per docs/deployment-plan.md (container + managed pg + static frontend;
   `ANTHROPIC_API_KEY` mandatory; single instance until session state externalizes).
10. Externalize conversation state → horizontal scaling (SDK session resume vs
    rebuild-from-messages decision).
11. Auth + multi-candidate (schema is already multi-candidate-shaped).
12. `strategy_convo` → subagent with its own context window (the documented
    tool→subagent evolution path).
13. Fine-tuning only if a trigger in docs/fine-tuning-proposal.md fires; until then
    grow the golden set and log per-capability cost/quality.
