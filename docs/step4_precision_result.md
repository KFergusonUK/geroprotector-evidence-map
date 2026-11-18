# Step 4 — precision of the resolver's auto-accepts: result

Protocol: `docs/step4_precision_protocol.md`, committed in `97c01bf` before the sample was
drawn. Adjudications, row by row: `data/reviews/step4_precision_sample.yaml`.
Adjudicated 2026-11-18 by one reviewer (Claude).

## Primary result: identity precision

**196 of 200 auto-accepts are the right compound: precision 98.0%, Wilson 95% CI
94.97%–99.22%. Four identity errors → CONDITIONAL** under the pre-registered bar
(0–3 GO, 4–5 CONDITIONAL, ≥6 NO-GO).

The protocol requires fixing the error classes found, then re-measuring on a fresh sample
of 200 before scaling. The result is CONDITIONAL; the pre-registered rule decides it.

## Limitation: the adjudicator wrote the resolver

The adjudicator (Claude) also wrote the matching rules being measured: single reviewer, no
blind, grading its own output. That is the weakest part of this method, and any bias it
introduces would make 98% optimistic in a direction that cannot be seen from inside. It
should have been stated in the protocol; it was not.

Mitigation (decided 2026-11-18, before any comparison): Kevin Ferguson adjudicates 30 of
the 200 rows, drawn at random, blind to these verdicts (`docs/step4_blind_check.yaml`).
Agreement on all 30: the number stands. Disagreement on two or more: the whole sample is
re-adjudicated by someone other than the resolver's author. One disagreement is reported
and resolved by discussion.

**Outcome (2026-11-18): 30 of 30 agree; the number stands.** Details and limits are in
`docs/step4b_precision_result.md`, "Blind checks".

## The four errors

| # | Trial | Compound | Registered as | What it actually is | Error class |
|---|---|---|---|---|---|
| 89 | NCT00899470 | metformin | name "Saxagliptin/Metformin, Fasting", otherNames [Onglyza, Glucophage] | fixed-dose combination tablet (description says FDC) | **combination slipped through**: the name-and-otherNames-agree rule (added in step 3) accepted a combination name because otherNames listed a metformin brand |
| 161 | NCT06235294 | resveratrol | name "Resveratrol" | *Polygonum cuspidatum* (knotweed) extract "yielding 100 mg/day resveratrol" | **extract named only in the description** |
| 184 | NCT01593605 | resveratrol | name "Resveratrol" | "a blend of low dose resveratrol and either leucine or HMB" | **blend named only in the description** |
| 165 | NCT02587741 | metformin | name "Metformin", otherNames [gliclazide MR, acarbose] | step-up regimen: metformin, then gliclazide, then acarbose | **regimen**: otherNames list other drugs while the name is a single compound |

Three of the four share one root cause: **auto-accept looks only at the name (and
otherNames), so a description that reveals an extract, a blend, a fixed-dose combination
or a regimen is never read.** The fourth (#89) is a rule of mine from step 3 that is too
permissive when the name itself is a combination.

## Secondary results (not gating)

**Systemic exposure: 190/196 correct (96.9%, CI 93.5–98.6%).** Errors: route words caught
in the wrong context (oral/IV aspirin classed *local* because "stent" appears in the
description; "topical" picked up from study text by the fallback; "nasal" from
nasogastric), and two local routes missed ("ventricular delivery"; an intravitreal
injection described only as "injected").

**Role: 132/168 correct where assigned (78.6%, CI 71.8–84.1%)**; 19 rows labelled
`unclear`, 9 ambiguous. Role is the resolver's weak point. Error patterns, roughly by
frequency:
- **"Active Comparator" used for the tested arm against placebo or no treatment** (about
  15): sponsors type the treatment arm ACTIVE_COMPARATOR when the comparison is
  drug vs placebo; the rule reads that literally as `comparator`.
- **Background drug present in every experimental arm** (about 6): metformin given in
  all arms of a trial testing something else, with no comparator-typed arm, reads as
  `experimental`.
- **Probe drugs in drug-interaction studies** (4): metformin as the PK probe reads as
  `experimental`.
- **Dose comparisons and bioequivalence** (about 5): "higher dose" or reference arms
  typed ACTIVE_COMPARATOR; BE crossovers.
- Registry linking errors and single-arm trials with a background drug (a few).

Role is not part of identity and did not affect the decision, but primary counts use
`experimental` only (§5.9), so a 21% role error rate would move headline numbers. It
needs fixing and measuring in its own right before §7 step 9.

## What CONDITIONAL requires next (per protocol)

1. Fix the error classes:
   - read the intervention description before auto-accepting; extract, blend, fixed-dose
     combination and regimen wording → review;
   - otherNames listing other drugs alongside a single-compound name → review;
   - never let the name-and-otherNames-agree rule accept a name containing "/" or "+"
     with another drug.
2. Add each error as a fixture case and a test.
3. Re-measure on a **fresh** sample of 200 (new seed, new population after the fix), under
   the same bar. Scale only on GO.

Each fix may move auto-accepts into review; that is the intended direction.
