# Phase 8 review notes — 2026-07-30

Two-axis review (Standards / Spec) of `ec59c70...HEAD` via parallel sub-agents,
followed by a fix batch and the two SPEC §10 manual reliability verifications.

## Findings fixed in this phase

| Finding (axis) | Fix |
|---|---|
| Dedupe permanently blocked retry of a `failed` document (Spec) | `ingest_upload` allows re-ingestion from the stored blob when status=failed; regression test added |
| `approval.conversation_id` never populated (both axes) | Gate passes `sdk_session_id` through; Pg repo resolves it to the conversation pk |
| Business logic in route handlers (Standards, SPEC §8) | Extracted `app/ingestion/service.py` (`ingest_upload`, `credentials_for_document`, `IngestionDeps` — also dissolves the data-clump smell) |
| No DB statement/connect timeout (both axes, SPEC §10) | `connect_args={"timeout": 5, "command_timeout": 15}` on the engine |
| No cost cap per call (Spec, SPEC §10) | `max_budget_usd` on both the main agent turn ($1.00) and stub one-shots ($0.30) — the SDK offers a dollar cap, not max_tokens; SPEC intent met in different units |
| Health omits agent component (Spec, SPEC §10) | `agent` component reports the session pool (approximation — see waivers) |
| `DocumentOut` built field-by-field ×3 (smell) | `_document_out(row)` helper |
| Primitive-obsession on credential kind (smell) | `CredentialKind` Literal on the Pydantic boundary; deleted the duplicate `_ALLOWED_KINDS` check |
| Committed `tsconfig.tsbuildinfo` (Spec) | Untracked + gitignored |
| SPEC/impl drift: status enum, audit wording, upload consent, commit style | SPEC amended (marked "P8 amendment") to record the implemented decisions |

## Waived, with reasons

- **Conventional Commits:** history is uniformly task-prefixed (`T4.2:`, `C6:`); rewriting
  19 commits is worse than recording the actual convention. SPEC §8 amended.
- **Full 3×-backoff DB retry:** `pool_pre_ping` transparently replaces dead pooled
  connections and asyncpg timeouts bound every call; an explicit retry loop around
  session acquisition adds complexity v1 doesn't need. Revisit at deployment.
- **Read-only tool calls in the approval table:** approval table stays a write-audit;
  invocations are in structured logs with request/session ids. SPEC §11 amended.
- **Agent health = session-pool report, not a live probe:** a real liveness probe would
  spawn a subprocess per health call. Dead clients leave the pool on failure, so pool
  state approximates truth. Follow-up: track last-successful-turn timestamp.
- **`resume_store` handles text, not PDFs:** the PDF path is the upload endpoint; the
  capability's promotion path (unify on the shared pipeline) is documented in the stub
  contract. Deliberate v1 split, now recorded in SPEC §4 context.
- **Dev DB password in compose:** local-only; deployment plan mandates secret manager.
- **`ApprovalPrompt.tsx` inlined into MessageList/ChatWindow:** functional parity;
  structure §7 was aspirational.

## Manual reliability verifications (SPEC §10)

**1. Anthropic API outage** — backend launched with `ANTHROPIC_BASE_URL` pointing at a
dead port; `POST /api/chat` kept the SSE stream alive (pings) and resolved to a readable
`error` event at the 120s turn timeout. No hang, no crash, no dropped stream. **PASS.**
Observation: the CLI retries internally rather than failing fast, so the user waits the
full timeout — bounded and honest, tightenable later.

**2. SDK subprocess death** — killed the bundled `claude.exe` (by exact path) mid-turn
while the agent was inside `strategy_convo`; the stream immediately delivered the
readable error event and completed. The next message on the same conversation received a
fresh session with the "(conversation was restarted…)" notice. **PASS.**

## Post-fix quality gates

50 unit + 4 integration tests green, ruff clean, mypy strict clean. Eval unchanged (94%).
