# Role 2: can a non-specialist apply the v2 role rules as the builder does?

**Fixed before any sampled row is viewed.** It is committed, together with the frozen
population, before the sample is drawn. It follows `docs/measurement_policy.md`.

## Why

Role-1 (`docs/role1_result.md`) found that role could not be shown to be reliable:
- agreement between two AIs was **Moderate** (κ 0.77);
- the human reader read background drugs as experimental on #8, #9 and #10. On #3 he was
  right and both AIs were wrong (erratum).

Since then:
- **headline counts no longer depend on role** (SPEC §5.9). Role is now a breakdown
  printed with its measured accuracy;
- **the rules were rewritten** (`docs/role2_rules.md`, v2, drafted by Codex, approved by
  Kevin Ferguson). They lead with five plain yes/no questions, ordered background first,
  each answered by pointing at words in the record.

Role-2 asks the question that now matters for that breakdown:

> **Do a careful non-specialist and the builder, both applying the v2 rules, agree on role?**

If they do, the rules carry their meaning without pharmacology training. If they do not,
the role breakdown stays "indicative", and the disagreements show where.

## Questions

1. **Primary, reliability:** Cohen's κ between Kevin Ferguson and Claude on the rows Kevin
   labels, with raw agreement and a confusion matrix.
2. **Secondary, resolver accuracy:** the resolver's role suggestion against the label on
   rows where the two readers agree (unclear excluded), and against each reader. Each has a
   Wilson 95% interval.
3. **Reported:** for each of the five questions, how often it decided the label, from the
   readers' notes.

## What is measured (frozen)

| Item | Value |
|---|---|
| Rules | `docs/role2_rules.md`, sha256 `8ee065c68537930e…` (v2, commit `cdbb56a`) |
| Resolver | resolver-v6, `data/rules/resolver.yaml` sha256 `81635ebaf6ebc5d7…` |
| Population | `data/measurements/role2_population.csv`, sha256 `db9a2711664621c4…`: every resolver-v6 auto-accept with a named intervention object (4,956), minus every unit **and every trial** already reasoned about: the step 4/4b samples, the role-1 packet, the role-1 calibration rows and the estriol census (518 units in 506 trials). **N = 4,339** |
| Resolver's suggested roles | `data/measurements/role2_resolver_roles.csv`, sha256 `0c6e178dac27ea7e…`. Neither reader opens it before labelling |
| Unit | one intervention object × one compound |

Whole trials are excluded, not just units. A reader who has seen a trial's record once
brings that reading to every other unit in it.

## Sample

- **n = 60,** drawn by `random.Random(20261127).sample(population, 60)` from the frozen CSV
  in file order. Code: `docs/role2_sample.py`; packet: `docs/role2_packet.yaml`.
- **The packet order is the random order,** so the first k rows are themselves a random
  sample.

## Readers and procedure

**Reader A: Claude.** It wrote the resolver's role logic and the role-1 rules (a
limitation); it did not write the v2 rules.
- It labels all 60 from the packet alone, using `docs/role2_rules.md`.
- Its labels are committed **before Reader B starts.**

**Reader B: Kevin Ferguson.**
- **Preparation:** read `docs/role2_rules.md` first, including the worked examples. That
  is the instrument; this is not a deviation.
- **Labelling:** in packet order, **without skipping**. A hard row is `unclear`, with a
  note. Stopping after any row k is allowed; later rows stay `null`. Aim for **k ≥ 30**.
- **Notes:** for every row, a `note` naming the question (1–5) that decided it. For
  example: `Q1: same 1000 mg in both arms`.
- **No help with rows:** no assistance from Claude, Codex or any other AI on any row.
  Questions about the *rules* may be asked and are answered by quoting
  `docs/role2_rules.md`, and every such question is listed in the result.
- **Commit:** the file is committed before the comparison is run.

**Codex** drafted the rules and is **not a reader** (`AGENTS.md`).

**Comparison** is run only after both files are committed: `python3 docs/role2_compare.py`.

## Labels

As in `docs/role2_rules.md`: `experimental`, `comparator`, `background` or `unclear`.

## Bar (decided now)

Primary: Cohen's κ, Kevin vs Claude, on Kevin's rows.

| Kevin's rows | κ | Finding |
|---|---|---|
| ≥ 30 | ≥ 0.80 | **Reliable**: a non-specialist and the builder apply the v2 rules alike. The role breakdown may be stated with its accuracy once in the methods, not beside each count, provided resolver accuracy also clears 90% with a Wilson lower bound ≥ 80% |
| ≥ 30 | 0.60–0.79 | **Moderate**: the breakdown is printed with its accuracy beside every figure |
| ≥ 30 | < 0.60 | **Not reliable**: the v2 rules do not carry their meaning to a non-specialist. The breakdown stays indicative, and the disagreements set the v3 agenda |
| < 30 | any | **Not established**: reported with its interval, without a band |

All disagreements are listed with both readers' notes.

## Analysis

`docs/role2_compare.py`, committed with this protocol:
- Cohen's κ with an approximate interval;
- raw agreement and the confusion matrix;
- resolver accuracy with Wilson intervals;
- the disagreement list;
- the tally of "which question decided it", taken from the notes.
