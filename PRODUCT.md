# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: the author — a software engineer running their own job search — using it as a
daily practical tool. Secondary (near-term): recruiters and interviewers seeing it as a
portfolio demonstration of engineering and product judgment. Aspirational (recorded, not
current): a scalable public product serving hundreds of users; infrastructure decisions
are made with that trajectory in mind, product decisions are not gated on it.

## Product Purpose

Amadeus is a multi-capability job-seeking agent: one conversational surface for resume
management (upload → decomposition into structured credentials), career strategy,
application tracking, job matching, and emotional support through the search. Success in
v1 = the author actually uses it during a real search, and it demos convincingly in an
interview setting.

## Positioning

Architecture-first personal agent: a pluggable capability registry (in-process MCP tools
on the Claude Agent SDK) where most capabilities are deliberate stubs that promote to
real features without touching routing, storage, or the frontend. Every agent-initiated
write passes a descriptive, human-approved gate with a full audit trail — a trust
mechanism neighboring "AI job tools" do not truthfully offer.

## Operating Context

Runs locally: React/Vite frontend (:5173) → FastAPI backend (:8000) → Claude Agent SDK
subprocess; Postgres (docker, host port 5433) + filesystem blob store. Sessions are
minutes-long chat exchanges plus occasional PDF uploads. Agent replies take 15–40s when
a capability fires — the interface must make waiting legible. Demo scenario: the author
walks a recruiter through chat → approval → stored credentials in under five minutes.

## Capabilities and Constraints

Five registered capabilities: resume_store (real; writes gated by approval),
strategy_convo, application_track, job_search_match, emotional_support (stubs — raw LLM
with capability prompts; identical contract, promotion-ready). Uploads: PDF only,
≤10 MB, text-layer extraction (OCR deferred). Approvals expire to denial after 90s.
Chat history persists but is not yet re-rendered after reload (known v1 gap). Single
user, no auth in v1. Budget-capped model calls.

## Brand Commitments

**Amadeus is a named character, not an anonymous tool.** The agent is referenced by
name, speaks with a distinct presence in messages, and may carry a visual mark in the
UI. The name evokes its namesake — virtuoso capability worn lightly. Voice: composed,
personable, quietly confident; a companion with expertise, never corporate-bland and
never cutesy. (User-confirmed 2026-07-30.)

## Evidence on Hand

Real working system (not vaporware): routing eval 94% (backend/tests/evals/REPORT-2026-07-30.md),
55 tests, live approval audit trail in Postgres. Synthetic fixtures only — no real
resume data exists in the repo, and none may be fabricated as marketing evidence.

## Product Principles

1. **Consent is the product.** Nothing is written without an explicit, plainly-worded
   approval; the audit trail is a feature, not plumbing.
2. **Stubs are honest.** Unbuilt depth is labeled, never faked; the container is the
   showcase.
3. **Waiting must be legible.** Long agent turns are the norm; the UI always shows what
   is happening and never leaves a silent gap.
4. **Fail loudly, recover quietly.** Errors are readable sentences; recovery is
   automatic and announced.
5. **Amadeus is present.** The character is felt in copy and interface details, at
   Operate-mode volume — presence, not performance.

## Accessibility & Inclusion

WCAG 2.1 AA is the binding working floor (user-confirmed 2026-07-30): contrast ≥4.5:1,
full keyboard operability, visible focus states, aria-live for streamed content,
screen-reader-coherent chat and approval flows.
