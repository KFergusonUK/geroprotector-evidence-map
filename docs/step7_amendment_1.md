# Step 7, amendment 1: scaled scope is the mammal universe

Amends `docs/step7_precision_protocol.md`, section "Population". Decided by Kevin
Ferguson on 2026-11-26 ("1 yes"), **before any scaled population existed**: nothing has
been fetched or resolved for scaled compounds, and the frozen-inputs table is still empty.
This is a dated amendment and is reported as a deviation from the original population
definition.

## The change

**Scaled compounds** are DrugAge Build 5 compounds that:
- are not in the seed fixture;
- resolve to a single molecular identity;
- **have at least one DrugAge row in a mammal species** (`species_taxon.tier = 'mammal'`,
  the SPEC §1.1 universe).

Count: **106 of 686** resolved scaled compounds.

The remaining 580 resolved compounds have only invertebrate, yeast or other non-mammal
evidence. They are **deferred**, not dropped: they keep their identities and synonyms in
`data/scale/`, and they can be added by a later amendment with its own measurement.

## Why

1. **No output path uses them.** Every headline cell (extension, harm, null, under-tested)
   is defined on the mammal universe (SPEC §1.1). Fetching trials for compounds that cannot
   appear in an output measures nothing that is reported.
2. **Fetch cost.** The count-only pass over all 2,852 scaled query terms summed 838,019
   hits (with overlap), a large share of the whole registry. The mammal-universe compounds
   need 678 terms after synonyms-v4.
3. **The measurement stays meaningful.** Precision is measured on the compounds whose
   counts are published.

## Effect on the rest of the protocol

**No change to:**
- the samples (R: 200 rows; C: 100 compounds);
- the bars;
- adjudication and the blind check;
- the reporting of seed and scaled results separately.

**C's compound frame is now the mammal-universe scaled compounds with at least one
auto-accept.** If fewer than 100 qualify, C is all of them, and the bar scales as already
specified. The scaled-down counts are written into the frozen-inputs commit.

**The "within the 159-compound mammal universe" secondary breakdown** now covers the whole
scaled population, so it is reported as that and not as a subset.

**Synonym rules at freeze:** synonyms-v4 (`data/rules/synonyms.yaml`), which adds the
ChEMBL word-like trade-name filter (208 names to review). The hash is recorded in the
frozen-inputs table.
