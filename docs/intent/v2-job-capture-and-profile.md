# v2 intent — job capture + profile layer

Confirmed via `interview-me`, 2026-07-30. This is the intent statement; SPEC.md §15
(spec-driven-development, next step) turns it into task boxes.

## Outcome

Two additions to Amadeus:

1. **Chat-native job-capture capability.** Paste a job posting's text into a chat
   message; the agent extracts structured `Job` data via a tool call.
   `job_search_match` is promoted from stub to real, matching/assessing fit against
   already-stored credentials. No separate upload UI — this happens inside the
   conversation, same as `strategy_convo`/`emotional_support`.
2. **Generic personal-profile data layer.** Structured facts about the user beyond
   resume credentials (goals, preferences, constraints, etc.), readable and writable
   through chat. Proven via round-trip: tell the agent something, ask it back later,
   get it right. Deliberately generic/domain-agnostic in schema — not hardcoded as
   "job-seeking preferences" — so a future mental-care or other individualized-service
   domain could read from the same table without a schema rewrite.

## User

The user, personally, as a daily job-hunting tool. Unchanged from v1 (PRODUCT.md:
primary = personal daily practical tool, secondary = recruiter-portfolio demonstration).

## Why now

The long-term vision (stated by the user during this interview) is job hunting +
individualized services + mental care combined into one platform. That's too large to
build directly. v2 grounds the platform in one genuinely real job-hunting slice *and*
lays the first real architectural groundwork (the personalization data layer) for the
bigger vision — deliberately a baseline, not the full vision.

## Success

Two live demos:
- Paste a real job posting → structured `Job` row → real match assessment against
  stored credentials.
- Tell the agent a personal fact/preference → stored in the profile layer → a later
  chat turn correctly recalls it.

## Constraint

- **8h pinned budget** (new number, on top of v1's ~13h10 + Phase 11's ~3h).
- Single-user — no auth, no multi-candidate work.
- No domain/subagent agent restructuring in v2 — insufficient room alongside the other
  two pieces when forced to prioritize (see "decisions" below).

## Out of scope

- Automated scraping/fetching of job data in any form (Google-result scraping,
  LinkedIn, even ATS JSON-endpoint polling). Manual paste only. See "decisions" for
  why this was ruled out rather than just deferred.
- Resume/JD tailoring flow (rewriting resume content for a specific posting) — related
  but separate; stays a future increment (already on the v1 roadmap as item 8).
- Mental-care features themselves — long-term vision, not this phase.
- Auth / multi-candidate.
- Matching actually consulting profile data — the data layer exists and round-trips,
  but `job_search_match` doesn't read it yet in v2. Wiring that up is a natural next
  increment once both pieces exist independently.
- Domain/subagent restructuring (the "how the agent is structured" half of the
  architecture-expansion question) — deferred to a later phase, not dropped. The one
  concession: the profile schema is designed generically so this restructuring stays
  possible later without a data migration.

## Decisions made during the interview (context for later)

- **Why not automated job-data fetching:** the user initially proposed Google-keyword
  search scraping, then a "gentle"/rate-limited fetch as a compromise. Both were ruled
  out once weighed against the *long-term* goal of a scalable product — ToS violation
  risk and enforcement exposure scale with commercial use in a way that "slow and
  polite" doesn't fix. Company-ATS JSON endpoints (Greenhouse/Lever-style) were raised
  as a lower-risk alternative but ultimately also passed over in favor of manual paste,
  which sidesteps the legal question entirely and is arguably a *better* freshness/
  authenticity signal — a posting the user personally found and pasted is inherently
  more verified than anything a scraper could infer. This was the original motivating
  problem (job platforms serving outdated/fake postings); manual paste addresses it by
  construction rather than by building freshness-detection heuristics.
- **Why the profile layer over domain/subagent restructuring:** both were named as
  "architecture for the bigger vision," but forced to prioritize one within 8h, the
  user chose the data layer — "individualized services" is fundamentally about the
  system knowing the person, not about agent process topology. Domain/subagent
  separation (the tool→subagent evolution path already named in the v1 roadmap, item
  12) remains a legitimate future direction, just not this increment's.
- **Why profile-write proven by round-trip only, not wired into matching:** keeps v2
  as two independently-demoable, separately-scoped pieces rather than one entangled
  feature — matches this project's incremental/vertical-slice discipline (CLAUDE.md).

## Next step

`spec-driven-development` — write this up as a SPEC.md §15 amendment with task boxes,
following the same pattern as §14 (Phase 11).
