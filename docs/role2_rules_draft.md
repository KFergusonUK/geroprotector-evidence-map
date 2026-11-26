# Role-2 rules draft

**Status: draft for Kevin's review.** This is a proposed explanation of how to label the
role of one named compound in one trial. It is not a role-2 protocol, sample, or result.
Approve or revise these rules before a new sample is drawn.

## The role question

For the named compound, ask: **what is this trial trying to learn, and what part does this
compound play in answering that question?** Read the trial purpose, intervention names and
descriptions, and arm descriptions together. A sponsor's arm-type label is evidence, not
the answer.

- **Experimental:** label the compound experimental when the trial is designed to evaluate
  its effect on participants, including a comparison of its doses, schedules, formulations,
  or an explicitly tested treatment that contains it; merely measuring the compound in the
  body does not make it experimental.
- **Comparator:** label it comparator when it is an active reference treatment against
  which a different intervention is being tested, rather than one of the treatments whose
  effects the trial compares.
- **Background:** label it background when it is standard care, a stable co-treatment, a
  probe or challenge used to measure something else, or another treatment present to
  support the main study question.
- **Unclear:** label it unclear when the registry does not let you decide among those roles
  without guessing what happened or what the sponsor intended.
- **Same compound, different dose or form:** if arms differ in the dose, schedule, or
  formulation of the named compound, it is experimental even when one arm is called
  “ACTIVE_COMPARATOR.”
- **Head-to-head active treatments:** when a trial compares two or more active treatments
  to learn which works better, label each compared treatment experimental for its own
  compound; reserve comparator for a reference/control treatment that is not itself part
  of the active head-to-head question. *Reason: this map asks what the trial tests about
  each compound, and a head-to-head trial tests each treatment's outcome.*
- **Bioequivalence:** label the test product experimental and its reference product
  comparator.
- **Compound in every arm:** if the same dose and form are given in every arm, it is usually
  background; if the arms differ in its dose, schedule, or form, it is experimental.
- **Combination treatments:** decide for the named compound, not just the combination's
  name; if its use is part of the assigned treatment being evaluated, it is experimental,
  while a stable co-treatment or component supplied across the comparison is background.
- **Single-arm or observational records:** the compound can be experimental when the study
  evaluates the effect of receiving it or of exposure to it; if the record only lists it
  without making its role clear, use unclear.
- **Do not infer from “open-label”:** that phrase means the treatment is not masked; by
  itself it says nothing about whether the treatment is experimental, comparator, or
  background.

## Worked examples of background

Each example quotes the registry packet used in role 1. The label is for the named compound
in that record, not a claim about whether the compound is medically important.

### Probe drugs in interaction studies — metformin, NCT01409395 and NCT03655301

NCT01409395 asks: “Does nizatidine affect the pharmacokinetics of metformin?” Participants
get metformin alone or with nizatidine. **Metformin: background**; the study tests what
nizatidine does to the probe drug, not metformin's therapeutic effect.

NCT03655301 says it studies “the effect the Bayer study drug, copanlisib, has on metformin.”
Metformin levels are measured after participants receive it with copanlisib. **Metformin:
background**; measuring its levels does not make metformin the treatment being tested.

### Challenge test given to everyone — captopril, NCT05442463

The intervention description says “Captopril challenge to each participant”; both groups
receive it during testing. **Role: background.** Captopril is a measurement challenge; the
study asks about hormone exposure and cardiorenal outcomes.

### Standard therapy in a device trial — aspirin, NCT01157455

The record says aspirin is taken “as a part of dual anti-platelet therapy”; the study is a
registry of an everolimus-eluting stent. **Role: background.** Aspirin is supporting care
around the device procedure, not the device being evaluated.

### Open-label add-on around the main treatment — empagliflozin, NCT04702490

The record says empagliflozin “will be incorporated into two of the treatment arms in an
open-label manner”; its arm labels pair it with both active and placebo MET409. **Role:
background in this role-1 example.** It is an open-label co-treatment in the MET409
comparison; being named in intervention lists or given without blinding does not, on its
own, make it the compound whose effect this record is testing.

## When `unclear` is the right label

`Unclear` is a valid result when registry information is missing, contradictory, or too
thin to establish the named compound's role. Do not fill gaps using what usually happens in
clinical practice.

- **NCT06199544, metformin:** the record links metformin to every group, while the group
  descriptions name metformin only for “Control group” and list Picolin and Rasoline for
  the others; the intervention links and group descriptions conflict. **Unclear.**
- **NCT01627431, aspirin:** aspirin and clopidogrel appear in a single antiplatelet arm,
  but the record does not establish whether aspirin is standard background or part of the
  tailored strategy being evaluated. **Unclear.**
- **NCT00021528, lithium:** the record lists lithium among several sequenced treatment
  options but has no registered arm groups or lithium-specific assignment detail.
  **Unclear.**
- **NCT01598337, aspirin:** the named aspirin-only arm suggests a comparator, but the
  record also says patients continue maintenance aspirin and links other antiplatelets to
  that arm; it does not say whether aspirin continues in the other arms. **Unclear.**

## Quick decision path

1. Is the compound itself being evaluated, or is it part of the assigned treatment under
   test? **Experimental.**
2. Is it the active reference against a different treatment? **Comparator.**
3. Is it a stable co-treatment, probe, challenge, or standard care for a different study
   question? **Background.**
4. Does the record leave those possibilities unresolved? **Unclear.**

When in doubt, add a short note pointing to the registry wording that decided the label, or
say exactly what the record leaves unknown.
