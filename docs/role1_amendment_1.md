# Role-1 amendment 1: a third reader, and a reader who may stop early

Amends `docs/role1_protocol.md`. Decided on 2026-11-26 by Kevin Ferguson, **before any
comparison between readers had been run**. At that point Reader A's labels were committed
(`885cfe1`), Reader B had labelled 14 of 100 rows and committed none, and Reader C did not
exist. Committed before Reader C sees the packet. Everything here is a deviation from the
pre-registered protocol and is reported as one.

**Order of events.** These are file times. The commit history shows when each file was
committed, not when it was written.

| Time (2026-11-26) | Event |
|---|---|
| 18:02 | This amendment and the Reader C prompt are written to disk |
| 18:11 | Reader C's output is saved (`role1_echo_raw.yaml`) |
| 18:13 | Reader C's output is imported (`role1_labels_echo.yaml`) |
| later | The amendment, then Reader C's labels, are committed, in that order |

The intention was to commit this amendment *before* Reader C saw the packet. It was
committed after. The rules here were fixed before Reader C's labels existed, but the
commit history cannot show that; the file times are the evidence. No comparison had been
run at any point before the commit.

Reader C returned the full packet rows with `label` and `note` filled in, not the short
format the prompt asked for. `role1_compare.py import-echo` accepted it: all 100 rows were
present, every label valid, and every note filled in.

## Why

Reader B (Kevin Ferguson) may not finish all 100 rows: labelling from registry text is slow
for a human. Reader C adds a second complete reading so that the full sample still gets two
independent readings. Reader B's rows, however many, remain the **human** check. The
original protocol made Reader B a human because Reader A (Claude) is an AI that wrote the
role rules. That reason still stands, and this amendment keeps the human check rather than
replacing it.

## Readers

| | Reader | Labels | Status |
|---|---|---|---|
| A | Claude | all 100 | committed `885cfe1` |
| B | Kevin Ferguson (human) | rows 1…k **in packet order**, k chosen by Kevin | in progress |
| C | "Echo", an AI assistant used by Kevin | all 100 | new |

**Reader B may stop after any row k.** The packet order is the order of
`random.Random(20261120).sample`, so rows 1…k are themselves a simple random sample of the
population. Reader B labels **in order and does not skip rows**: a row that is hard to call
gets `unclear` and a note. Skipping hard rows would bias agreement upward. Rows after k are
left `null`, and the file is committed with them null.

**Reader C conditions:**
- **Model:** its name and version are recorded in the result. If it is a Claude model, the
  result says so, because agreement between A and C would then be partly one model family
  agreeing with itself.
- **Inputs:** C receives only `docs/role1_packet.yaml` and the prompt
  `docs/role1_echo_prompt.md`, verbatim. It gets no repository access, no other reader's
  labels, and no calibration material.
- **Saving its output:** C's output is saved as `data/reviews/role1_labels_echo.yaml` and
  committed before any comparison. Kevin does not read C's output before committing his
  own labels. Either he runs C after committing his file, or he saves C's output unread.

**Calibration.** On 2026-11-26, after labelling 14 rows, Kevin asked whether he was
"doing it right". Two things followed:
- **On row #15**, Claude declined to comment on the specific row. It did state that the
  written rules do not settle head-to-head multi-arm trials.
- **Calibration offered.** Claude offered five calibration rows from the step-4 and 4b
  samples, outside the population (`docs/role1_calibration.yaml`). Each exercises one
  written rule, and no head-to-head trial is included.

If Kevin uses the calibration rows, his rows after that point were labelled after training.
He records the row id at which he did the calibration (a note on that row), and the result
reports agreement before and after it where n allows.

## Analysis (decided now)

1. **Pairwise Cohen's κ** for each pair of readers, on the rows both labelled, with raw
   agreement and a confusion matrix. **Fleiss' κ** for all three, on the rows all three
   labelled.
2. **The protocol's κ bands apply to each pair with n ≥ 30.** A pair with n < 30 is
   reported but not banded, because the interval is too wide.
3. **The finding is the lowest banded pairwise κ.** The reliability of the rules is limited
   by the pair of readers who agree least.
4. **If Reader B labels fewer than 30 rows,** the result states that role reliability rests
   on agreement between two AIs only. That is weaker evidence: the two can share
   interpretations and blind spots, so agreement may be inflated. The result may not
   describe role as "reliable" on that basis alone.
5. **Human vs AI is reported separately on Reader B's rows.** If B–A or B–C agreement is
   materially below A–C on the same rows, the result states that AI agreement does not
   establish reliability for human readers of the rules. "Materially below" means the two
   κ intervals do not overlap.
6. **Resolver accuracy** (secondary), with a Wilson 95% interval in each case:
   - on rows where every reader who labelled the row agrees, `unclear` excluded;
   - against each reader separately.
7. **Every disagreement is listed with all readers' notes,** as before.
