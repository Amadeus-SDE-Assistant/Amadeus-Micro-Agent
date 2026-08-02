# v2 summary & roadmap

Covers everything since v1 closed: **Phase 11** (gap-closing, ~3h, SPEC §14) and
**Phase 12** (v2 proper, 8h box, SPEC §15). Both landed on `v1.5` and merged into
`dev-v3` (PRs #3, #4). Supersedes the roadmap section of
[v1-summary.md](v1-summary.md), which is now partly stale — see the reconciliation
table below.

Handoff point: `dev-v3`, 20 commits ahead of `main`, working tree clean.

## What v2 adds

| Delivered | Phase | Evidence |
|---|---|---|
| `job_capture` — paste a posting in chat → structured `Job` row | 12 | `source=user_pasted`, `raw` holds requirements/location; live-demoed through the approval gate |
| `job_search_match` promoted stub → real | 12 | Optional `job_id`; assesses fit against stored credentials, citing real bullets and dates |
| `profile_fact` layer — generic personal-fact store | 12 | `profile_save`/`profile_recall`; round-trip proven **across a fresh conversation** |
| `application_track` promoted stub → real | 11 | `JobRepository` + `ApplicationRepository`, no-dedup by design |
| OCR fallback for scanned resumes | 11 | Tesseract + `pytesseract`; `extraction_method=ocr` end-to-end |
| Chat history re-render on reload | 11 | `GET /api/conversations/{id}/messages` + localStorage hydration |
| **Security: SDK built-in tools disabled** | 11 | Bash/Read/Write/Edit were reachable with **zero approval**; fixed with `tools=[]`, regression-tested RED→GREEN |

Registry grew **5 → 8 capabilities**; 3 of 8 are now real writes behind the approval
gate (`resume_store`, `application_track`, `job_capture`) plus `profile_save`.

Quality gates at close: **79 backend tests** (72 unit + 7 integration, up from 51 at
v1), mypy clean (42 files), ruff clean on all touched files, frontend `tsc` + build
clean, routing eval **89%** (17/19) against the ≥80% gate.

## What the process caught that tests didn't

Worth preserving — each of these argues for keeping a specific ritual:

- **A live smoke test caught a grounding bug that unit tests passed straight through**
  (T12.6). The credential formatter dropped `body.bullets`, so the model truthfully
  reported "no data" on skills that *were* stored. The tests asserted the capability
  returned text; only a real run showed the text was wrong. → *Keep the live demo
  requirement at checkpoints.*
- **The routing eval caught a cross-capability regression** (T12.7). `profile_recall`'s
  tool description said "…or when a saved preference would help answer their
  question" — permissive enough to hijack routing from `strategy_convo` and
  `application_track`. Nothing else would have surfaced this. → *Keep the golden set
  growing with every new tool.*
- **The security hole (T11.0) was found by accident**, mid-verification of an unrelated
  task. `ApprovalGate`'s "no registered write-intent = read-only, allow" rule was
  written for 4 read-only stubs and silently applied to the SDK's built-ins too.
  → *A permissive default is a vulnerability, not a convenience.*

## Honest gaps (recorded, not hidden)

**Design decisions that will bite eventually**

1. **No link between `job_capture` and `application_track`.** Capturing a posting and
   then logging an application for the same role creates **two unrelated `Job` rows**.
   The no-dedup rule was a deliberate T11.2 call, but v2 added a second write path into
   the same table, which sharpens the problem. This is the most likely source of
   user-visible confusion today.
2. **`JobRepository.list_for()` ignores `candidate_id`** and returns every `Job` row.
   Correct under the single-candidate assumption, silently wrong the moment a second
   candidate exists. The signature accepts the argument so the fix is contained, but
   it is not implemented.
3. ~~**`job_search_match` does not read the profile layer.**~~ **CLOSED 2026-08-01 by
   Phase 13** (SPEC §16). Both branches now consult `profile_fact`; fit assessments name
   conflicts against stored constraints. Note Phase 13 also found an unplanned P0 while
   demoing it — `setting_sources` defaulted to loading the developer's own
   `~/.claude/settings.json`, whose `defaultMode: auto` was auto-approving writes past
   the approval gate. See SPEC §16 T13.0.

**Carried from v1, still open**

4. pgvector columns exist and stay unpopulated (deferral item 4).
5. Approval works only while the originating stream is open — no reconnect-and-resume.
6. No auth; single implicit candidate.
7. No idle-session reaper — subprocess memory is unbounded over a long session.

**Process / housekeeping**

8. **Phase 12 has no recorded actual time.** Every prior phase closed with actual-vs-box
   (`~115m vs 150m`). Phase 12's boxes summed to 6h40 against an 8h pin, but wall-clock
   was never tracked. A real break in the ritual, unrecoverable now.
9. **`uv run mypy app` fails on this machine** — a Windows Application Control policy
   blocks the `mypy.exe` shim, not the package. Use `uv run python -m mypy app`.
   [README.md](../README.md) and [CLAUDE.md](../CLAUDE.md) still document the broken form.
10. **`ruff format --check .` fails repo-wide** on ~10 files no recent phase touched — a
    ruff version bump since Phase 11. Per-file checks on recent diffs are clean.
11. **`main` is 20 commits behind `dev-v3`.** v1 is the only thing shipped there.
12. `gh` CLI is not installed — PRs are manual via compare links.

## v1 roadmap reconciliation

| v1 item | Status |
|---|---|
| 1. Push `dev`, PR to `main` | ✅ done (PR #2) |
| 2. History re-render on reload | ✅ done (T11.1) |
| 3. `technical_qa` stub | ⬜ still open |
| 4. Idle-session reaper | ⬜ still open |
| 5. Promote `application_track` | ✅ done (T11.2) |
| 6. OCR fallback | ✅ done (T11.3) |
| 7. Promote `job_search_match` | ◐ **partial** — real matching shipped (T12.6), but text-based; pgvector still deferred |
| 8. Resume/JD tailoring | ⬜ still open — still the highest direct user value |
| 9–13. Deploy, scale-out, auth, subagents, fine-tuning | ⬜ all still open |

## Future improvements

**Near-term (hours each)**

1. **Wire `job_search_match` → profile layer.** The explicit v2 deferral. Both halves
   exist; this is one function body plus golden-set cases. Highest value-per-hour item
   on this list.
2. **Merge `dev-v3` → `main`.** 20 commits of working, demoed, unshipped work.
3. **Fix the documented mypy invocation** in README/CLAUDE.md; consider a Windows note
   alongside the existing landmines section.
4. **Reconcile repo-wide ruff formatting** in one isolated commit, so future
   `--check .` runs are meaningful again.
5. `technical_qa` stub — one file, one registry line, two golden cases.
6. Idle-session reaper in `AgentService`.

**Mid-term (the promotion ladder continues)**

7. **Link captured jobs to applications** (gap 1). Probably a `job_capture` result the
   agent can pass into `application_track`, mirroring how `application_id` already
   flows between turns. Decide dedup policy deliberately — the current "never dedup"
   was right for one write path, not two.
8. **pgvector population + semantic match** (deferral item 4). The trigger condition
   named at v1 has now genuinely fired: real `Job` rows with real `jd_text` exist.
9. **Resume/JD tailoring** — v1's item 8, still unbuilt, still the highest direct user
   value now that both stored credentials *and* stored job descriptions exist.
10. **Profile-aware capabilities generally** — `strategy_convo` and `emotional_support`
    reading `profile_fact` is what starts making "individualized" true rather than
    aspirational.

**Longer-term — and the actual v3 decision**

The stated long-term vision is *job hunting + individualized services + mental care* on
one platform. v2 deliberately built the **data** half of that foundation (a
domain-agnostic `profile_fact` store) and deferred the **structural** half. So:

11. **Domain/subagent restructuring** — the deferred half of the v2 architecture
    question. Moving from one flat capability list to domain-scoped subagents is what
    lets a mental-care domain exist without entangling job-hunting code. The
    `profile_fact` schema was kept generic specifically so this stays possible without
    a migration. This is the gateway item.
12. **The mental-care / individualized-services domain itself** — blocked on 11, or at
    least much cheaper after it.
13. Deploy per [deployment-plan.md](deployment-plan.md); auth + multi-candidate (fixes
    gap 2); externalize conversation state; fine-tuning only if a
    [proposal](fine-tuning-proposal.md) trigger fires.

**The question v3 should answer first:** does v3 do the restructuring (item 11, opening
the door to mental care), or keep deepening job-hunting (items 7–10, compounding a
working product)? Both are defensible. They are not the same phase, and picking both is
how an 8h box becomes a 20h one.
