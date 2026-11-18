# Step 4b — precision re-measurement after resolver-v2: protocol

**Fixed before any sampled row was viewed**; committed ahead of the sample being drawn.
Required by the CONDITIONAL result of step 4 (`docs/step4_precision_result.md`): fix the
error classes found, then re-measure on a fresh sample of 200 under the same bar.

## What is measured (frozen)

| Item | Value |
|---|---|
| Code | git `3106996` |
| Resolver | `resolver-v2`, `data/rules/resolver.yaml` sha256 `af9ce22a97a0b73e…` |
| Fixture | `data/fixtures/seed_compounds.yaml` v0.6.0, sha256 `59af19e6d7cdf724…` |
| Registry data | unchanged from step 4 (API 2.0.5, data 2026-11-10; 120 query strings; 10,796 studies) |
| Population | `resolver_match` rows with `decision = 'auto_accept'` (4,973), **excluding the 190 units already adjudicated in step 4**: **N = 4,783** |
| Unit | one row = one intervention object × one compound |

## Sample

Simple random sample without replacement, **n = 200**, by
`random.Random(20261119).sample(rows, 200)` over the eligible population ordered by
(`nct_id`, `idx`, `compound_key`); code `docs/step4b_sample.py`. Excluding step-4 units
makes the sample fresh: no unit is judged twice. As before, no per-compound claim.

## Adjudication

Exactly as in step 4 (`docs/step4_precision_protocol.md`, "Adjudication"): identity is the
primary judgement; a different molecule, placebo, fixed-dose combination presented as a
single agent, extract or food, or class or regimen is incorrect; **ambiguous counts as
incorrect**; route is not part of identity. Role and route are not judged in this round:
role gets its own protocol (§5.9), and route is not gating.

**Stated limitation:** the adjudicator (Claude) wrote the resolver. Single reviewer, not
blind, grading its own rules. Mitigation, fixed now: Kevin Ferguson adjudicates 30 of the
200 at random (seed 2026111930), blind to these verdicts. All 30 agree: the number stands.
One disagreement: reported and resolved by discussion. Two or more: the whole sample is
re-adjudicated by someone other than the resolver's author. Until that check is done the
result is **provisional**.

## Bar (unchanged from step 4)

| Identity errors in 200 | Decision |
|---|---|
| 0–3 | **GO**: scale (§7 step 7) |
| 4–5 | **CONDITIONAL**: fix and re-measure again |
| ≥ 6 | **NO-GO**: rethink matching before scaling |

No sensitivity arguments: the count under this rule decides.
