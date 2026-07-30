# Fine-tuning proposal — Amadeus Micro Agent

Date: 2026-07-30 · Author: v1 build · Status: **decided — do not fine-tune yet**

## Question

Should any part of Amadeus be served by a fine-tuned model rather than prompted
frontier models?

## Current evidence

- Routing (the most classifier-shaped task in the system): **94% accuracy** on the
  golden set with prompting alone — tool descriptions + system prompt, no examples
  ([eval report](../backend/tests/evals/REPORT-2026-07-30.md)). The one "miss" was a
  mislabeled golden case.
- Credential decomposition: strict JSON contract against a Pydantic schema; first-run
  success on real fixtures; failures are handled (status=failed, no partial writes),
  not silent.
- Cost: ~$0.20–0.35 per capability turn under `max_budget_usd` caps; single-user
  volume ≈ dollars per week.
- Training data on hand: **zero** labeled real-world examples (synthetic fixtures
  only, by policy).

## Analysis

1. **Fine-tuning cannot fix the actual hard problem.** The product's ceiling is
   grounding — real job postings, real application state — which is retrieval and
   tool work, not weights.
2. **The measured tasks are already above target.** Routing sits 14 points over
   threshold; spending on a custom router buys headroom nobody is short of.
3. **No data.** Serious fine-tuning wants thousands of verified pairs; v1 has 16
   golden utterances and a no-real-resume-data policy. The eval harness is precisely
   the instrument that will *accumulate* that dataset as usage grows.
4. **Cheaper levers are untouched.** Prompt iteration, model tiering (e.g. Haiku for
   decomposition — likely 10× cheaper, schema-validated so quality is checkable),
   prompt caching, and golden-set growth all precede fine-tuning on cost-per-quality.

## Verdict

**Not yet.** Prompting + schema validation + evals beats fine-tuning at this scale on
every axis: quality (94%), cost (pennies), flexibility (stub promotion changes
behavior by editing a prompt, not retraining), and risk.

## Trigger conditions that reopen this decision

| # | Trigger | Response |
|---|---|---|
| 1 | Routing accuracy sustained **<80%** across ≥500 real labeled utterances *after* prompt/description iteration | Fine-tune a small classifier for routing only |
| 2 | Decomposition validation-failure rate >5% on real resumes after prompt iteration and a Haiku-tier trial | Fine-tune a small model on verified text→credential pairs (needs ≥5k pairs) |
| 3 | Monthly model spend exceeds the fully-loaded cost of training + serving a tuned model for a narrow high-volume subtask | Cost-driven fine-tune of that subtask only |
| 4 | A capability needs stable voice/behavior that measurably drifts across frontier-model upgrades | Evaluate tuning vs. pinning + eval-gated upgrades (prefer the latter) |

Until a trigger fires, the standing instruction is: grow the golden set with every
stub promotion, and log per-capability cost/quality so trigger 1–3 are measurable
rather than vibes.
