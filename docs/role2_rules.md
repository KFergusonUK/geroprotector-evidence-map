# Role-2 rules v2

**Status: approved by Kevin.** These rules explain how to label the role of one named
compound in one trial. They are not a role-2 protocol, sample, or result.

## The role question

For the named compound, ask: **what is this trial trying to learn, and what part does this
compound play in answering that question?** Read the trial purpose, intervention names and
descriptions, and arm descriptions together. A sponsor's arm-type label is evidence, not
the answer.

## Decision path

Answer these questions in order, using words in the registry rather than assumptions about
usual medical practice:

1. **Is the same dose and form of the compound given in every arm, without the record
   comparing its use?** If yes, label **background**. *Look at each arm's description and
   intervention list.*
2. **Does the record say it is a probe or challenge, or describe it as supporting care for
   a different treatment, device, or study question?** If yes, label **background**. *Look
   at the purpose, intervention description, and arm descriptions.*
3. **Does the record call it the control, reference, standard, or usual treatment, or does
   the title frame a new treatment versus it as standard care?** If yes, label
   **comparator**. *Look at the title and arm descriptions; an `ACTIVE_COMPARATOR` label
   alone is not enough.*
4. **Does the record say it evaluates this compound's effect, compares its presence with
   its absence, or compares its dose, schedule, or form?** If yes, label **experimental**.
   *Look at the purpose/title and the differences between arms.*
5. **Do the record's words still leave its role uncertain or contradictory?** If yes, label
   **unclear** and note what is missing. *Point to the conflicting or absent purpose, arm,
   or intervention detail.*

For a head-to-head trial, each treatment being tested is **experimental** unless the record
identifies one as the control, reference, standard, or usual treatment under question 3.
*Reason: the registry's stated comparison tells us which compounds the trial tests.*

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
- **Head-to-head active treatments:** label each treatment experimental unless the record
  calls one the control, reference, standard, or usual treatment, or frames the title as a
  new treatment versus standard care; arm-type labels alone do not decide this. *Reason:
  the registry's stated comparison tells us which compounds the trial tests.*
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

### Open-label does not decide the role: #3 and #43

**#3, empagliflozin (NCT04702490): experimental.** The title says “MET409 Alone or in
Combination With Empagliflozin”; empagliflozin is added in two arms, so its addition is
part of the comparison. “Open-label” means unmasked, not background.

**#43, aspirin (NCT07275749): background.** Acetyl-leucine arm: “... an open-label loading
300 mg aspirin ... a maintenance dose of 100 mg aspirin ...”; placebo arm: “... an open-label
loading 300 mg aspirin ... a maintenance dose of 100 mg aspirin ...”. Aspirin is the same;
the trial compares acetyl-leucine with placebo.

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

When in doubt, add a short note pointing to the registry wording that decided the label, or
say exactly what the record leaves unknown.
