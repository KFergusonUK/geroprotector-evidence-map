# Step 7 — precision of auto-accepts under automatically generated synonyms: protocol

**The design is fixed before the scaled synonym pipeline is built.** It was committed
before any scaled population existed. The "Frozen inputs" table is the only part filled in
later. Its values are written in a separate commit, together with the frozen population
files, **before the sample is drawn**. Nothing else here changes after this commit. Follows
`docs/measurement_policy.md`.

## Why this needs its own measurement

The 99.5% from step 4b (`docs/step4b_precision_result.md`) was measured on the **seed
fixture**: 22 compounds whose synonyms, negatives and review lists Claude curated by hand
and Kevin Ferguson reviewed. Scaling (SPEC §7 step 7) matches registry text against
synonyms **generated automatically** from DrugAge, ChEMBL and PubChem for about 1,000
compounds.

That is not a marginal change to the matcher. It changes **what the matcher is matching
against**. PubChem synonym lists are notoriously noisy. They carry trade names from many
markets, supplier and catalogue codes, depositor-assigned identifiers, names of mixtures
and related substances, and sometimes entries that are simply wrong (step 3 found PubChem
titling Y-27632's record "Ximelegatran"). The resolver auto-accepts a clean exact match on
a synonym. With a hand fixture, every synonym had been checked. Now no synonym has been.

**The prior does not transfer in either direction.** Two differences between the seed set
and the scaled set pull opposite ways:

- **The seed set was chosen to be hard.** Many seed compounds are naming nightmares:
  rapamycin and the rapalogs, 17-α vs 17-β estradiol, NDGA and masoprocol, lithium salts,
  the NR/NMN abbreviations. A typical DrugAge compound is easier. *This pushes scaled
  precision up.*
- **The seed fixture was clean.** Its hard cases were met with hand-written
  `must_not_match`, `needs_review` and decoy lists. The scaled set has none of that, and its
  synonyms are unreviewed. *This pushes scaled precision down.*

We do not know which effect dominates. 99.5% is therefore **not a prior for the scaled
set**, either as a floor or as a ceiling. Treating it as carrying over would be the
largest methodological error available at this point. It would also be invisible until
someone audited the output.

## Questions

1. **Primary (gating), row-weighted:** of the auto-accepts for scaled compounds, what
   fraction are the right compound? This is directly comparable with steps 4 and 4b.
2. **Primary (gating), compound-weighted:** across scaled compounds, how often is a typical
   auto-accept the right compound? A row-weighted sample is dominated by high-volume
   compounds. A dirty synonym on a compound with five trials can make that compound's whole
   row in the output wrong, yet a row-weighted sample of 200 would rarely see it. Both
   estimands are needed.
3. **Secondary (reported, not gating):**
   - precision broken down by the **source of the synonym that produced the match**
     (DrugAge name / ChEMBL preferred name or synonym / PubChem synonym), which tests the
     PubChem-noise hypothesis directly;
   - precision within the 159-compound mammal universe (SPEC §1.1);
   - the count of **cross-compound synonym collisions**: one string generated for two or
     more compounds. These must never auto-accept, and any that did is reported.

## Population (defined now; frozen later)

- **Scaled compounds:** every DrugAge Build 5 compound that is not in the seed fixture and
  that resolves to a **single molecular identity** (full InChIKey, SPEC §5.1).
  - DrugAge entries that are extracts, diets, mixtures or otherwise lack a single identity
    get **no automatic synonyms**. They cannot auto-accept, and their matches go to review
    only.
  - The pipeline document records how many entries fall here.
- **Population:** every `resolver_match` row with `decision = 'auto_accept'` for a scaled
  compound, under the frozen code, rules and synonym set. Seed-compound rows are excluded,
  since they were measured in steps 4 and 4b.
- **Unit:** one intervention object × one compound, as in steps 4 and 4b.
- The population is written to `data/measurements/step7_population.csv` in a fixed order
  (`nct_id`, `idx`, `compound_key`), hashed, and committed before sampling. The policy says
  the population file is frozen and committed alongside the protocol. This is that file.

## Samples

| Stratum | Draw | n | Seed |
|---|---|---|---|
| **R** (row-weighted) | simple random sample of population rows | 200 | `random.Random(20261121)` |
| **C** (compound-weighted) | simple random sample of scaled compounds having ≥ 1 auto-accept; then one auto-accept per drawn compound, drawn uniformly from that compound's rows | 100 | `random.Random(20261122)`: compounds first, then rows in compound order |

- If the population has fewer than 200 rows, R is the whole population. If fewer than 100
  compounds have auto-accepts, C is all of them. The bar's error counts then scale
  proportionally, rounding down to the GO side only where a count is exactly on a
  boundary. The scaled-down counts are written into the frozen-inputs commit before
  sampling.
- A row drawn into both R and C is adjudicated once and counts in both.
- Code: `docs/step7_sample.py`. It reads the frozen CSV only, never the live database, so
  the sample stays reproducible after the population changes. This fixes a weakness of
  step 4.

## Adjudication

- **Identity rule:** unchanged from `docs/step4_precision_protocol.md`, with ambiguous
  counted as incorrect.
- **Reference identity:** the "right compound" is the DrugAge compound as resolved to its
  full InChIKey, with salts collapsing to the parent. An intervention that administers a
  stereoisomer, analogue, prodrug or related substance sharing a synonym is
  **incorrect**. Examples:
  - alpha-linolenic acid matched as "ALA" for alpha-lipoic acid;
  - a vitamin E form other than the DrugAge one;
  - an extract matched by its marker compound's name.
- **Recorded for each row:** the verdict, a note, and the matched synonym together with its
  source. The source comes from the frozen synonym table, not from the adjudicator.

**Readers.** Claude adjudicates all rows. Claude also built the resolver and the synonym
pipeline, which is stated as a limitation, as in steps 4 and 4b. Claude's verdicts are
committed before any blind packet is generated.

**Blind check (decided now, improved on steps 4 and 4b).** Kevin Ferguson judges a packet
without seeing Claude's verdicts. The packet holds:

1. **30 rows drawn at random** from R ∪ C (`random.Random(20261123)`);
2. **every row Claude judged incorrect** in R ∪ C, up to 15, chosen at random if there are
   more.

The two sets are shuffled together, and the packet does not say how many rows are of
either kind.

In steps 4 and 4b, no original error fell in the blind draw, so agreement on "incorrect"
was never tested. Part 2 tests it.

Outcomes:
- **Random 30:** 0 disagreements and the numbers stand. 1 disagreement is discussed and
  resolved. 2 or more and R and C are both re-adjudicated in full by someone other than the
  pipeline's author.
- **Claude's incorrect rows:** every disagreement is discussed and listed in the result.
  If Kevin judges correct a row Claude called incorrect, Claude's call was too strict. That
  biases precision down, not up, and is reported as such.

## Bar (decided now)

Both primary strata must pass. The overall decision is the **worse** of the two.

**R (n = 200):** the same bar as steps 4 and 4b.

| Identity errors | Precision | Wilson 95% lower bound | Decision |
|---|---|---|---|
| 0–3 | ≥ 98.5% | ≥ 95.7% | GO |
| 4–5 | 97.5–98.0% | 94.3–95.0% | CONDITIONAL |
| ≥ 6 | ≤ 97.0% | ≤ 93.6% | NO-GO |

**C (n = 100):**

| Identity errors | Precision | Wilson 95% lower bound | Decision |
|---|---|---|---|
| 0–1 | ≥ 99.0% | ≥ 94.6% | GO |
| 2–3 | 97.0–98.0% | 91.5–93.0% | CONDITIONAL |
| ≥ 4 | ≤ 96.0% | ≤ 90.2% | NO-GO |

The decisions mean:
- **GO:** load scaled compounds into the outputs. Every published count from scaled
  compounds carries the measured R precision and interval, kept separate from the seed
  figure.
- **CONDITIONAL:** fix the error classes found. Each fix becomes a pipeline filter or a
  fixture case, plus a test. Then re-measure on fresh samples (new seeds, new population).
  This applies under the policy because synonym-pipeline fixes can add as well as remove
  auto-accepts. A pure downgrade (a new filter that only removes synonyms or blocks
  acceptance) needs no re-measurement and turns the last result into a floor, as in 4b.
- **NO-GO:** the automatic synonyms cannot be trusted to auto-accept. Scaled compounds go
  through review only, or the pipeline is redesigned and measured again.

**Rationale for C's bar.** C has half R's n, so its interval is wider. Its GO line (at most
1 error, lower bound ≈ 94.6%) is set close to R's GO lower bound (≈ 95.7%), so that a
compound-weighted GO is no easier to earn than a row-weighted one. A bar based on point
estimates alone would have to allow 1.5 errors, which cannot happen.

## After the number exists

- **Every compound with an error in R or C gets its full synonym list audited.** Every
  synonym that produced a wrong match becomes a filter case or a negative, plus a test.
  Like step 4, this changes the pipeline and does not revise the measured number.
- **Seed and scaled figures are always reported separately.** They measure different
  things, for the reasons above, and are never pooled into a single precision figure.
- **Recall is not measured here.** Noisy synonyms also drive the registry *queries*. A
  separate recall check, if wanted, gets its own protocol.

## Frozen inputs (filled in a separate commit before sampling)

| Item | Value |
|---|---|
| Code | git `…` |
| Resolver rules | `data/rules/resolver.yaml`, version `…`, sha256 `…` |
| Synonym pipeline | rules/version `…`; synonym table sha256 `…`; sources and their dates `…` |
| Seed fixture (excluded compounds) | `data/fixtures/seed_compounds.yaml` v`…`, sha256 `…` |
| Registry data | ClinicalTrials.gov API `…`, data date `…`; query strings `…`; studies `…` |
| Scaled compounds | `…` resolved to a single identity; `…` without one (review only) |
| Population | `data/measurements/step7_population.csv`, sha256 `…`; **N = …** rows over `…` compounds |
| Scaled-down bar | only if R < 200 rows or C < 100 compounds; otherwise "not needed" |
