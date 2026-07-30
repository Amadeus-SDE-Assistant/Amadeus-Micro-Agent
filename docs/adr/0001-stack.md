# ADR-0001: Stack — FastAPI + Claude Agent SDK + Postgres/pgvector + React/Vite

Date: 2026-07-30 · Status: accepted (implemented through v1)

## Context

An architecture-first job-seeking agent: five capabilities behind one conversational
surface, most stubbed, all promotion-ready. Budget ~14h. The author explicitly wanted
the Claude Agent SDK (its agent loop, sessions, tools, and permission system) rather
than hand-rolling a tool loop. Initial plan was Java/Spring Boot; it was dropped the
moment the SDK requirement landed, since the SDK ships for Python and TypeScript only.

## Decision

- **Backend: Python + FastAPI.** The SDK is async-first (an async message stream per
  turn); FastAPI is async-native and SSE falls out of it naturally. Django's batteries
  (ORM/admin/auth) were overhead for a v1 with a repository layer of its own.
- **Agent runtime: Claude Agent SDK, `ClaudeSDKClient`.** One persistent session per
  conversation (multi-turn context, `interrupt()` support). `query()` is reserved for
  one-shot stub bodies. Capabilities register on an in-process MCP server
  (`create_sdk_mcp_server`) — no subprocess or network hop; a capability is one
  decorated async function.
- **Postgres 16 + pgvector (Docker), JSONB-heavy schema.** The data is genuinely
  relational (candidate→credentials→applications→events); JSONB absorbs resume-shaped
  schema churn; pgvector columns exist unpopulated so future matching needs no
  migration. Mongo's flexibility argument was neutralized by JSONB; its vector story
  costs a managed dependency.
- **Blob storage: filesystem behind a `BlobStore` Protocol.** PDFs never enter DB
  rows; the S3/MinIO swap is one class.
- **Frontend: React + Vite + TS, no state library, no CSS framework.** Two surfaces
  don't justify either.

## Consequences

- **The SDK spawns a Claude Code CLI subprocess** (bundled inside the wheel — no
  separate install). Two Windows consequences, both discovered live: the backend must
  run under the Proactor event loop (`run.py` pins it; `--reload` is unavailable
  because reload mode installs the Selector loop, which cannot spawn subprocesses),
  and Alembic conversely pins the Selector loop for asyncpg migrations.
- **Deployment shape is a real container** (Python runtime + bundled CLI), not a
  serverless function; session state lives in the subprocess → single instance or
  sticky sessions for now (see deployment plan).
- **Auth:** dev rides the machine's Claude Code login; any deployed product must use
  `ANTHROPIC_API_KEY` per Anthropic's terms.
- **Cost control** is `max_budget_usd` per turn/call — the SDK exposes a dollar cap,
  not `max_tokens` (P8 finding).
- Repository Protocols + one shared conformance suite (memory vs Postgres) keep unit
  tests at ~5s/zero tokens while integration tests hit a dedicated `amadeus_test` DB.
