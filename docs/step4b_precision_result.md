# Step 4b — precision re-measurement after resolver-v2: result

Protocol: `docs/step4b_precision_protocol.md` (committed `df4a823` before the sample was
drawn). Adjudications: `data/reviews/step4b_precision_sample.yaml`.

## Result

**199 of 200 auto-accepts are the right compound: precision 99.5%, Wilson 95% CI
97.22%–99.91%. One identity error → GO** under the pre-registered bar (0–3 GO).

**Status: provisional.** The adjudicator (Claude) wrote the resolver. Per the protocol, the
result becomes final only after Kevin Ferguson's blind check of 30 rows
(`docs/step4b_blind_check.yaml`); two or more disagreements send the whole sample to an
independent re-adjudication. The same applies to the step-4 sample
(`docs/step4_blind_check.yaml`).

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

## Follow-up (per protocol)

The error becomes a fixture case and a test (resolver-v3: extract disqualifier covers
"extracted"/"extraction"; "wheat germ" added to spermidine's review list). The change is
downgrade-only: it can only move auto-accepts to review, never add one. It is still a
change to the resolver; whether it needs its own measurement before scaling is Kevin
Ferguson's call, recorded here rather than assumed.

Role (78.6% accuracy in step 4) is a separate measured problem with its own protocol, and
is not addressed by this result.
