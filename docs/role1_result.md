# Role 1: can a trial's role for a compound be assigned reliably from registry text? Result

**Protocol:** `docs/role1_protocol.md` (committed `7dc230e` before sampling), as amended by
`docs/role1_amendment_1.md` (`f26aa33`).

**Label files:**
- Reader A, Claude: `885cfe1`.
- Reader C, Echo (GPT-6): `c34fdce`.
- Reader B, Kevin Ferguson: `98d4d7c`.

**Comparison:** `python3 docs/role1_compare.py`, run 2026-11-26 after all three files were
committed.

## Result

| Pair | n | Raw agreement | Cohen's κ (approx. 95%) | Band |
|---|---|---|---|---|
| Claude vs GPT-6 | 100 | 87/100 = 87.0% | **0.768** (0.65–0.89) | **Moderate** |
| Claude vs Kevin | 15 | 10/15 = 66.7% | 0.202 (−0.37–0.77) | not banded (n < 30) |
| GPT-6 vs Kevin | 15 | 8/15 = 53.3% | 0.139 (−0.33–0.60) | not banded (n < 30) |

Fleiss' κ across all three readers on the 15 rows they share is 0.321.

**Finding, under the pre-registered rules: MODERATE.** The lowest banded pairwise κ is 0.768
(Claude vs GPT-6). Role assignment from registry text is usable **only with a stated
accuracy figure attached to every role-filtered count**.

**Rule 4 of the amendment applies.** Fewer than 30 rows had a human reader, so this rests
on agreement between two AIs. **Role may not be described as reliable.**

**Resolver accuracy (secondary).** Every role-filtered count carries this figure. It is
below the 90% level at which the figure could be stated once in the methods instead.

| Compared with | Correct | Wilson 95% |
|---|---|---|
| Rows where every reader agrees (unclear excluded) | 60/83 = **72.3%** | 61.8–80.8% |
| Claude | 63/98 = 64.3% | 54.4–73.1% |
| GPT-6 | 64/98 = 65.3% | 55.5–74.0% |
| Kevin | 11/15 = 73.3% | 48.0–89.1% |

## The human reader's rows: a strong signal, not a demonstrated result

Reader B differed from both AIs on five rows, and **on every one of them he said
`experimental`**. On #14, Claude said comparator and GPT-6 said unclear. **On the other four,
both AIs said `background`:**
- #3, empagliflozin given open-label in both arms;
- #8, aspirin as standard dual antiplatelet therapy in a stent trial;
- #9, a captopril challenge test given to all participants;
- #10, metformin as the probe drug in a drug-interaction study.

The written rules name all of these as background. Recognising them in a registry record
takes pharmacology conventions that the rules name but do not teach.

Rule 5 of the amendment asks whether human–AI agreement is materially below AI–AI
agreement, meaning the κ intervals do not overlap. **By that test it is not shown.** With
n = 15, the intervals overlap, so this is reported as a signal. The point estimates
(0.20 and 0.14 against 0.77) and the consistent direction make it the most important
qualitative result here. AI–AI agreement shows that two models read the rules alike. It does
not show that the rules carry their meaning to a careful human reader.

**Reader B's account of #10, given after all labels were committed:** "I noted Metformin as
the drug, description said subjects will be dosed with metformin alone, so it's the primary
test." The rule's wording, "the trial is *testing* this compound", reads naturally as "the
trial *measures* this compound". In a drug-interaction study, the probe drug is exactly the
compound that gets measured. The rule needs to define experimental by *purpose*: the trial
evaluates the compound's effect on the participants.

## Disagreements between the AIs: where the rules are silent or misapplied

**Head-to-head trials: the rules are silent.**
- **Rows:** #11 lithium vs quetiapine, #15 captopril vs propranolol and timolol, #75
  sirolimus vs cyclosporine, #78 lithium vs valproate vs carbamazepine.
- **Labels:** Claude said experimental, and so did Kevin where he labelled the row. GPT-6
  said comparator.
- **Why:** the rules do not say whether every compared drug is experimental or whether the
  title's framing decides it. Reader B raised this case himself, at #15, before any
  comparison.

**An explicit rule misapplied.**
- **#20, metformin immediate- vs extended-release:** the rules say arms differing by the
  compound's formulation make it experimental. GPT-6 said comparator.

**Records that cannot be decided.**
- #17, a single-arm tailored antiplatelet strategy.
- #61, where the registry links every drug to every arm.
- #14, where metformin is the control but is linked to every arm.
- #52, which has no registered arms.

The readers split between `unclear` and a best guess.

**Other splits.** Other bioequivalence and combination structures (#49, #76), a
pharmacogenetics study (#33) and a component of standard-therapy control (#82). Claude's
own notes flagged #33, #65, #68, #74 and #91 as places where a literal reading of the rules
and the study's intent diverge.

## Limitations

- **Reader A (Claude) wrote the role rules and the resolver's role logic.** Its labels are
  the most likely to share the resolver's reading.
- **Reader C (GPT-6) was added after sampling** (amendment 1). Its labels were produced
  before the amendment was committed. The amendment was written first, at 18:02, against
  Reader C's output at 18:11, as the file times show. GPT-6 also returned four generic
  sentences as notes, not the row-specific reason the prompt asked for, so its labels cannot
  be audited row by row. Its agreement with Claude should carry less weight than the number
  suggests.
- **Reader B labelled 15 of 100 rows.** He stopped because the task was slow and he was
  unsure of the rules. That is itself evidence about the rules.
- **Reader B asked about #15 while labelling.** Reader A declined to comment on the row and
  said the rules do not cover head-to-head trials. Five calibration rows were offered
  (`docs/role1_calibration.yaml`). Reader B did not use them: the calibration file has no
  labels.
- **A comparison test run before the readers were compared printed Reader A's real labels
  for rows #10–#38.** It was a synthetic test of the script, built on Reader A's file.
  Reader B reports not having seen that output.

## What follows

1. **Role-filtered counts are reported with the resolver's measured accuracy beside each
   one:** 72.3% (61.8–80.8%) against reader consensus. Counts that ignore role are reported
   alongside them.
2. **Role rules v2, to be measured afresh as role-2 with a new sample:**
   - **define experimental by purpose:** the trial evaluates the compound's effect on the
     participants;
   - **add a head-to-head clause;**
   - **add short worked examples of background:** a probe drug in an interaction study, a
     challenge test, standard therapy in a device trial, a drug given open-label in every
     arm;
   - **design role-2 so a human reads at least 30 rows,** after the examples and before any
     comparison.
3. **The resolver's role logic is not changed on the strength of this result.** It was not
   what was measured, and changing it would need its own diff and check.
