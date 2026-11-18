# Measurement policy

Standing rules for every measurement in this project (precision, role, and any later
ones). They apply to each protocol unless it explicitly says otherwise, and a protocol
cannot relax them.

## 1. Pre-registration

The protocol — population, sample size, seed, adjudication rules, and the decision bar —
is committed before any sampled row is viewed. The bar decides the outcome; no
sensitivity argument after the fact ("it would have passed if…") is used to soften it.

## 2. Frozen population

Every protocol commits its **population file** (one row per unit, with the identifiers the
sampler draws from) alongside the protocol, before sampling. The sampler reads that file,
not the live database. Reason: re-running the resolver changes the live population, so a
sampler that rebuilds it cannot reproduce its own sample (found 2026-11-18: the step-4
sample could no longer be regenerated after resolver-v2).

## 3. What triggers re-measurement

- **Any change that can add an auto-accept triggers re-measurement, always.**
- **Downgrade-only changes do not.** A change that can only move matches from accept to
  review (or reject) cannot lower precision: it touches only rows that would otherwise have
  been counted, and it removes a known error class. After such a change, the last measured
  precision is reported as a **floor**, not a point estimate. Re-measuring every
  downgrade-only fix would make the protocol unfalsifiable in practice — it would never end.
- Whether a change is downgrade-only is shown by tests (e.g. the description-asymmetry
  property test), not asserted.
- **Every resolver change is diffed against the previous decisions before it is
  committed.** `python -m agesdk resolve` reports, row by row (intervention × compound),
  every decision transition, rows added and gone, `is_combination` changes and the count
  of **new auto-accepts**. A change claimed downgrade-only is run with
  `--downgrade-only`, which **rolls the whole run back** if it would add a single
  auto-accept. The diff, with its transitions, goes in the commit message. Every
  transition class is read, not only the auto-accept count: the diff has caught two error
  classes before commit (resolver-v4's first placebo rule rejected real administrations,
  "X then placebo" and "X + placebo"; resolver-v5's showed an unexpected review → rejected
  class, which on inspection was correct). Tests show the change does what was intended;
  the diff shows what else it did.

## 4. Adjudicators

- **Where the judgement has a checkable ground truth** (compound identity: PubChem,
  ChEMBL, the registry record), a single adjudicator is acceptable *only* with a blind
  check: a second person adjudicates a random 30 without seeing the first verdicts. All
  agree → the number stands; one disagreement → discussed; two or more → the whole sample
  is re-adjudicated by someone other than the author of the rules being measured.
- **Where the judgement is interpretive** (role: tested arm vs comparator vs background,
  read from inconsistent sponsor text), agreement between independent readers *is* the
  measurement. Two adjudicators label the full sample independently, each committing their
  labels before seeing the other's. Inter-rater agreement is reported. Disagreements are
  evidence that the rule is underspecified, not errors to be resolved away.
- The author of the rules being measured is always named as such in the result.

## 5. Results

A result states the number with its interval, the decision under the pre-registered bar,
its status (provisional until any required check is done), and the limitations — including
who adjudicated.
