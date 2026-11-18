# Step 4 — precision of the resolver's auto-accepts: protocol

**Fixed before any sampled row was viewed.** Committed to the repository ahead of the
sample being drawn; the commit history is the timestamp. Nothing below may change after
the sample is seen. Any later change to the rules is a new measurement on a new sample.

## Question

Of the intervention-to-compound matches the resolver **auto-accepts**, what fraction are
the right compound? This is SPEC §7 step 4, the go/no-go for scaling (§7 step 7).

## What is measured (frozen)

| Item | Value |
|---|---|
| Code | git `5f20cd8` |
| Resolver | `resolver-v1`, `data/rules/resolver.yaml` sha256 `108843f9f72391a4…` |
| Fixture | `data/fixtures/seed_compounds.yaml` v0.5.0, sha256 `baff32838dcf8e29…` |
| Registry data | ClinicalTrials.gov API 2.0.5, data 2026-11-10; 120 query strings; 10,796 studies |
| Population | every `resolver_match` row with `decision = 'auto_accept'`: **N = 5,252** |
| Unit | one row = one intervention object × one compound |

## Sample

Simple random sample without replacement, **n = 200**, drawn by
`random.Random(20261118).sample(rows, 200)` from the population ordered by
(`nct_id`, `idx`, `compound_key`). The sampling code is `docs/step4_sample.py`.

Simple random sampling estimates precision over auto-accepts as they occur, so it is
weighted towards the high-volume compounds (metformin, aspirin, semaglutide). It does not
estimate per-compound precision; no per-compound claim will be made from it.

## Adjudication

One reviewer (Claude), reading for each row the intervention object as registered (name,
`otherNames`, description, type) plus the study title and arm groups.

**Primary judgement — identity.** Correct if the intervention administers the matched
compound itself: any salt, hydrate, formulation, brand or sponsor code of that molecule
(§5.1 salt collapse; lithium salts collapse to Li⁺). **Incorrect** if it is any of:
a different molecule (including stereoisomers and analogues), a placebo or dummy, a
fixed-dose combination product presented as a single agent, an extract or food rather
than the compound, or a class or regimen rather than the compound. **Ambiguous counts as
incorrect.** Route is not part of identity: a drug-eluting stent carrying sirolimus *is*
sirolimus here (route is judged separately).

**Secondary judgements, reported but not gating:**
- *Role* (§5.9) against the arm groups: is `experimental` / `comparator` / `background`
  right? Accuracy is computed over rows not labelled `unclear`; the `unclear` rate is
  reported separately.
- *Systemic exposure* (§5.6): is `systemic` / `local` / `unclear` right?

Every judgement is recorded with a note in `data/reviews/step4_precision_sample.yaml`.

## Bar (decided now)

Primary metric: identity precision = correct / 200, with a Wilson 95% interval.

| Identity errors in 200 | Precision | Wilson 95% lower bound | Decision |
|---|---|---|---|
| 0–3 | ≥ 98.5% | ≥ 95.7% | **GO**: scale (§7 step 7) |
| 4–5 | 97.5–98.0% | 94.3–95.0% | **CONDITIONAL**: fix the error classes found, then re-measure on a fresh sample of 200 before scaling |
| ≥ 6 | ≤ 97.0% | ≤ 93.6% | **NO-GO**: rethink matching before scaling (§7 step 4) |

Rationale: a false join poisons every downstream count (§5.1). At the GO boundary the
data are consistent with an error rate under about 4%; above it, a compound with a
thousand auto-accepted trials could be carrying dozens of wrong ones.

## After the number exists

Each identity error found becomes a fixture case (`must_not_match` or `needs_review`) and a
test, so it cannot recur. That changes the resolver, and therefore requires a new sample
to measure; it does not revise this number.
