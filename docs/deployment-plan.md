# Deployment plan — local → cloud

Date: 2026-07-30 · Status: plan only (nothing implemented; that is the point —
SPEC §3 requires the architecture be verifiably cloud-portable, not deployed).

## Mapping

| Local piece | Cloud target | Migration cost |
|---|---|---|
| React + Vite build | Static hosting/CDN (Cloudflare Pages, Vercel, S3+CloudFront) | `npm run build` output is already static; point `/api` at the backend origin |
| FastAPI + Agent SDK | **Container** on Cloud Run / Fly.io / ECS | Dockerfile below; the one non-standard constraint |
| Postgres (compose, :5433) | Managed Postgres with pgvector (Neon, Supabase, RDS) | Set `AMADEUS_DATABASE_URL`; run `alembic upgrade head` as a release step |
| Blob store (`FsBlobStore`) | S3 / R2 / GCS | Implement the 2-method `BlobStore` Protocol against the SDK of choice; swap in lifespan |
| `.env` / dev defaults | Platform secret manager | Config is already `pydantic-settings`, env-prefixed `AMADEUS_` |

## The non-standard constraint, updated by build findings

The Agent SDK runs the agent loop in a **Claude Code CLI subprocess**. Findings from
the actual build that simplify/shape deployment:

1. **The CLI is bundled inside the Python wheel** (`claude_agent_sdk/_bundled/`) —
   platform-specific binary selected at install. A plain `uv sync` in a Linux image
   gets the Linux binary. No Node install, no separate CLI install. (Simpler than the
   spec's original assumption.)
2. **Event loop discipline:** the app must start via `run.py` (pins the Proactor
   loop on Windows; harmless on Linux) and must never run under `uvicorn --reload`.
   In a container this is moot — but keep `CMD ["python", "run.py"]`, not a reload
   command.
3. **Auth:** `ANTHROPIC_API_KEY` is **required** in deployment — Anthropic's terms do
   not permit claude.ai subscription login for products. Dev-only convenience (CLI
   login) does not carry over.
4. **Session state lives in the subprocess pool** → one instance (or sticky
   sessions) for now. Horizontal scaling needs externalized conversation state (the
   `conversation`/`message` tables already exist; SDK session resume is the open
   question from SPEC §12) — explicitly a post-v1 concern.
5. **Memory sizing:** each active conversation holds a CLI subprocess; size the
   container for peak concurrent sessions, and consider an idle-session reaper
   (drop clients after N minutes; the restart-notice path already handles revival).

## Dockerfile sketch (backend)

```dockerfile
FROM python:3.12-slim
RUN pip install uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ .
ENV AMADEUS_DATA_DIR=/data
# ANTHROPIC_API_KEY, AMADEUS_DATABASE_URL injected by the platform
EXPOSE 8000
CMD ["uv", "run", "python", "run.py"]
```

Release step: `uv run alembic upgrade head` against the managed DB before rollout.

## Observability next steps (deferred, per SPEC §10)

Structured JSON logs already ship with request/session ids — point the platform's log
drain at stdout. First additions post-v1: a metrics endpoint (request latency,
per-capability cost from the `done` events, approval decision rates) and trace ids
propagated into the SDK calls. The `approval` table is already an audit surface.

## Rollback

Container images are immutable and the DB is Alembic-versioned: rollback = previous
image + `alembic downgrade` (the initial migration's downgrade path is tested).
Blobs are append-only; no rollback interaction.
