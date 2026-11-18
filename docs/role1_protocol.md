# Role 1 — can a trial's role for a compound be assigned reliably from registry text?

**Fixed before any sampled row was viewed**; committed, with the frozen population, before
the sample is drawn. Follows `docs/measurement_policy.md`.

## Why this is its own measurement

Primary counts use role `experimental` only (§5.9), so role moves headline numbers. In
step 4 the resolver's suggested role was right 78.6% of the time where assigned. Unlike
compound identity, role has no external ground truth: "is this the tested arm, the
comparator, or background therapy?" is a judgement about sponsor intent from inconsistent
text. **Agreement between two independent readers applying the same written rules is the
measurement.** Disagreements are evidence that the rules (or the registry text) are
underspecified — not errors to be resolved into a truth.

## Questions, in order

1. **Primary — reliability:** do two readers, applying the rules below independently,
   agree on role? Measured by Cohen's κ over the four labels, with raw agreement.
2. **Secondary — resolver accuracy:** how often does the resolver's suggested role match
   the label, (a) on rows where both readers agree, and (b) against each reader separately.
   Reported with Wilson 95% intervals.

## What is measured (frozen)

| Item | Value |
|---|---|
| Code / rules | resolver-v3, `data/rules/resolver.yaml` sha256 `66e09a09697ec622…` |
| Population | `data/measurements/role1_population.csv` (sha256 `a3e1caedaf121793…`): every resolver-v3 auto-accept (4,943) minus the 387 units already judged in steps 4 and 4b: **N = 4,556** |
| Resolver's suggested roles | `data/measurements/role1_resolver_roles.csv` (sha256 `daab68f15fa794ca…`), frozen for the secondary comparison; readers must not open it before labelling |
| Unit | one intervention object × one compound |

## Sample

**n = 100** (enough to see whether agreement is workable; two full manual readings), by
`random.Random(20261120).sample(population, 100)` with the population read from the
frozen CSV in file order. Code: `docs/role1_sample.py`. Packet: `docs/role1_packet.yaml`.

## Readers and procedure

- **Reader A: Claude** (wrote the resolver's role rules — stated as a limitation).
  **Reader B: Kevin Ferguson.**
- Each reader labels all 100 from the packet alone (registry record as registered; no
  resolver output), writes labels to `data/reviews/role1_labels_<reader>.yaml`, and
  **commits them before seeing the other reader's file.** The commit history is the record.
- Comparison only after both files are committed: `python3 docs/role1_compare.py`.

## Labelling rules (what both readers apply)

Label the role of **the named compound** in **this trial**, judged from the registry record
(intervention objects, arm groups and their descriptions, title, summary).

- **experimental** — the trial is testing this compound: it is what differs between the
  arms being compared (including different doses, regimens or formulations of it), or the
  object of study in a single-arm or observational study where it is the exposure. Also a
  test product in a bioequivalence study.
- **comparator** — an active control: the compound is given in a comparison arm against
  which another intervention is judged. Includes the reference product in a
  bioequivalence study.
- **background** — given to participants regardless of which arm they are in, or as
  standard care, co-medication, rescue medication, or a probe substrate in a drug-interaction
  study; i.e. present but not what is being tested.
- **unclear** — the record does not allow a decision between the above.

Guidance, decided now:
- **Sponsor arm types are evidence, not the answer.** An arm typed ACTIVE_COMPARATOR that
  contains the compound against placebo or no treatment is `experimental`.
- If the compound appears in every arm, it is `background` unless the arms differ by its
  dose, regimen or formulation (then `experimental`).
- If the compound is part of a combination being tested against a component, judge the
  compound's own role (e.g. metformin present in both "drug X + metformin" and "placebo +
  metformin" is `background`).
- Use `unclear` rather than guessing.

## Bar (decided now)

Primary, Cohen's κ (four labels):

| κ | Finding |
|---|---|
| ≥ 0.80 | **Reliable**: role can be assigned from registry text by these rules. |
| 0.60–0.79 | **Moderate**: usable only with a stated accuracy figure attached to every role-filtered count. |
| < 0.60 | **Not reliable**: role cannot be assigned reliably from registry text. Every role-filtered count carries a stated accuracy figure and is presented as indicative; that is a finding, not a failure to fix quietly. |

Secondary (resolver accuracy on rows both readers agree on, excluding `unclear`): reported
with its interval in every case. Whatever the κ band, **role-filtered counts carry the
resolver's measured accuracy figure**; ≥ 90% (Wilson lower bound ≥ 80%) is the level at
which that figure may be stated once in the methods rather than beside each count.

All disagreements are listed in the result with both readers' notes.
