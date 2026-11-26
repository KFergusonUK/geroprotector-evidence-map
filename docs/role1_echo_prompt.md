# Prompt for Reader C (give this verbatim, followed by the packet file)

You are one of several independent readers labelling clinical-trial registry records. Each
reader works alone. There is no "right answer key" you can see; do not try to guess what
anyone else would say.

The attached file `role1_packet.yaml` contains 100 rows. Each row is one trial from
ClinicalTrials.gov and one named compound (the `compound` field). The `intervention`
block is the registry entry that names that compound; `all_interventions`, `arm_groups`,
`title` and `summary` are context.

For EVERY row, label the role of **the named compound** in **that trial**, using exactly one
of these four labels:

- **experimental**: the trial is testing this compound. It is what differs between the arms
  being compared (including different doses, regimens or formulations of it), or the object
  of study in a single-arm or observational study where it is the exposure. Also the test
  product in a bioequivalence study.
- **comparator**: an active control. The compound is given in a comparison arm against
  which another intervention is judged. Includes the reference product in a
  bioequivalence study.
- **background**: given to participants regardless of which arm they are in, or as standard
  care, co-medication, rescue medication, or a probe substrate in a drug-interaction study.
  That is, present but not what is being tested.
- **unclear**: the record does not allow a decision between the above.

Guidance:
- Sponsor arm types (EXPERIMENTAL, ACTIVE_COMPARATOR, ...) are evidence, not the answer. An
  arm typed ACTIVE_COMPARATOR that contains the compound against placebo or no treatment is
  `experimental`.
- If the compound appears in every arm, it is `background` unless the arms differ by its
  dose, regimen or formulation (then `experimental`).
- If the compound is part of a combination being tested against a component, judge the
  compound's own role (e.g. metformin present in both "drug X + metformin" and "placebo +
  metformin" is `background`).
- Use `unclear` rather than guessing.
- Judge only from the record provided. Do not look anything up.

Output: YAML only, no commentary before or after, in exactly this form, one entry per row,
all 100 rows, in the packet's order:

```yaml
rows:
- id: 1
  label: experimental
  note: "one short sentence: why"
- id: 2
  label: background
  note: "..."
```

The `note` is required for every row. Keep it to one sentence, and say what in the record
decided it. If you need to work in batches, output rows 1-25, then 26-50, and so on, in
the same format, and I will join them.
