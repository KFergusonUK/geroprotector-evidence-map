# Step 4b — precision re-measurement after resolver-v2: result

Protocol: `docs/step4b_precision_protocol.md` (committed `df4a823` before the sample was
drawn). Adjudications: `data/reviews/step4b_precision_sample.yaml`.

## Result

**199 of 200 auto-accepts are the right compound: precision 99.5%, Wilson 95% CI
97.22%–99.91%. One identity error → GO** under the pre-registered bar (0–3 GO).

**Status: final (2026-11-18).** The adjudicator (Claude) wrote the resolver, so the
protocol made the result provisional until Kevin Ferguson's blind check of 30 rows
(`docs/step4b_blind_check.yaml`). **Blind check: 30 of 30 agree; the number stands.**
See "Blind checks" below.

## The error

| # | Trial | Compound | Registered as | What it is |
|---|---|---|---|---|
| 158 | NCT07662330 | spermidine | name "Spermidine" | wheat-germ concentrate: "extracted from … wheat germ using a 100:1 concentration process", 5 mg spermidine per capsule |

Same class as step 4's extract errors. resolver-v2's description disqualifier matched
"extract"/"extracts" but not "extracted", and the fixture's "wheat germ extract" did not
appear verbatim.

## Gaps seen that did not produce identity errors

otherNames carrying a *different* substance with no INN stem — "tresiba once daily"
(insulin degludec), "Folic acid" — pass v2's other-drug rule. Identity was correct in both
(the compound is administered), but the rule is narrower than its intent.

## Follow-up: resolver-v3, applied after measurement

The error became a fixture case and a test: resolver-v3 widens the extract disqualifier to
"extracted"/"extraction"/"concentrate", and adds "wheat germ" to spermidine's review list.
The change is **downgrade-only** (it can only move auto-accepts to review; auto-accepts
4,973 → 4,943), so under `docs/measurement_policy.md` §3 it does **not** trigger
re-measurement (decided by Kevin Ferguson, 2026-11-18). **Under resolver-v3, 99.5% is a
floor, not a point estimate.**

**Scaling decision:** scale (§7 step 7) on this result. The blind check cleared on 2026-11-18.

Role (78.6% accuracy in step 4) is a separate measured problem with its own protocol, and
is not addressed by this result.

## Blind checks (steps 4 and 4b)

Kevin Ferguson judged 30 randomly drawn rows from each sample, blind to the original
verdicts. Run with `python3 docs/step4_blind_compare.py 4|4b`.

| Round | Rows | Agree | Disagree | Outcome |
|---|---|---|---|---|
| 4 | 30 | 30 | 0 | number stands (98.0%, CONDITIONAL) |
| 4b | 30 | 30 | 0 | number stands (99.5%, GO) |

How the verdicts were recorded: Kevin typed 6 directly into the step-4 file. The other 54
were transcribed by Claude from his message "Both blind checks all correct". Each file
header says so.

What this does and does not show:
- **It shows** that the author's "correct" calls are not inflated. That was the bias the
  check was set up to catch, because it would make precision look better than it is.
  Across 60 rows the author called correct, the independent reader found no wrong compound.
  The disagreement rate is 0/60, with a Wilson 95% upper bound of 6.0%.
- **It does not show** whether an independent reader would catch the errors. None of the
  five original identity errors fell in the blind draws. That was expected: about 0.6
  errors are expected in step 4's 30 rows and about 0.15 in step 4b's. So agreement on
  "incorrect" calls was not tested. That gap could only make the precision figures too
  low, not too high.
