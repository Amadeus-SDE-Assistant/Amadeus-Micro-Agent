# ADR-0002: Approval gate — descriptive intents, batch granularity, and the allowed_tools trap

Date: 2026-07-30 · Status: accepted (implemented through v1)

## Context

The binding user requirement (SPEC §11): ask before **any** write, and ask in intent
language — "can I edit this experience section to be more concise?" — never a raw
payload dump. A resume ingestion produces ~20 credential rows; 20 prompts would make
the tool unusable.

## Decision

1. **Batch granularity.** Approval is granted per capability call, covering that
   call's whole declared write set. One resume → one approval → many audited rows.
2. **Descriptive intents as registry metadata.** Each write capability declares an
   intent-builder (`args → one plain sentence`) in the capability registry. A
   capability that cannot describe its write in one sentence is doing too much — the
   rule doubles as an architectural smell test. Capabilities without an intent
   builder are read-only and skip the gate.
3. **Two consent paths, one guarantee.** Agent-initiated writes pause the turn via
   the SDK's `can_use_tool` callback → approval card in the chat stream → resume or
   refuse. Direct REST uploads treat the user's explicit upload action as the consent
   (the UI says so on the control). Nothing is ever written without a human action.
4. **Queue-merge turn architecture.** While the gate blocks the SDK turn awaiting a
   decision, the SDK message iterator yields nothing — so AgentService merges SDK
   messages and gate events onto one asyncio queue per turn, letting the
   `approval_request` event reach the SSE stream mid-block.
5. **Expiry = denial.** Unanswered approvals resolve to `expired` (deny) after 90s —
   deliberately below the 120s per-gap turn timeout, so expiry always resolves before
   the hang detector fires. Every decision (approved/denied/expired) lands in the
   `approval` audit table, linked to its conversation.

## The trap (why this ADR exists)

**`allowed_tools` bypasses `can_use_tool` entirely.** An entry there auto-approves
the tool before the permission callback is consulted. Our first live demo wrote
credentials with *no approval prompt* because `resume_store` was listed. The fix —
write tools must never appear in `allowed_tools`; they reach the callback precisely
by *not* being pre-allowed — is pinned by a regression test, and the SDK's own
`CanUseToolShadowedWarning` (observed later in eval runs) confirms the semantics.

Two durable lessons: unit tests could not have caught this (the gate logic was
correct; the configuration silently routed around it) — only the live checkpoint
demo did; and permission-adjacent configuration deserves the same review scrutiny as
permission code.

## Consequences

- Adding a write capability = one tool function + one intent builder + exclusion
  from `allowed_tools` (automatic — the allowed list is derived by filtering out
  write tools).
- The approval table doubles as an observability surface (SPEC §10).
- Denials are graceful by construction: the model receives a deny message and
  narrates it ("No problem — I won't save that one"), verified live.
