# Synonym pipeline for scaled compounds (SPEC §7 step 7): design

This document defines what `docs/step7_precision_protocol.md` measures. It is a **draft
until approved**. Choices marked **[decide]** are judgement calls for Kevin Ferguson. Once
approved, the rules live in a versioned file (`data/rules/synonyms.yaml`), and its hash
goes into the step-7 frozen inputs.

## Scope

- **In scope:** every DrugAge Build 5 compound (1,046 names) **except** the 23 seed fixture
  entries. The hand-curated fixture stays authoritative for those 23, and no generated
  synonym is ever added to a seed entry.
- **Unit of output:**
  - one `compound` row per resolved identity (full InChIKey);
  - `compound_synonym` rows tagged with every source that produced the string.

## Stage 1 — identity (no judgement calls; mechanical)

Each DrugAge name goes through these steps:
1. **PubChem name → CIDs.**
2. **Parent CID** (salt and hydrate collapse, SPEC §5.1).
3. **Properties:** the full InChIKey and molecular formula.

Outcomes are recorded for every name:

| Outcome | Meaning | Gets automatic synonyms? |
|---|---|---|
| `resolved` | exactly one parent CID, single component | yes |
| `ambiguous` | the name maps to several parent CIDs | no: review only |
| `not_found` | PubChem knows no such name (extracts, diets, many mixtures) | no: review only |
| `mixture` | the parent is still multi-component (formula contains "."), or PubChem has no parent | no: review only |
| `seed` | already a seed fixture entry | the fixture applies |

Two further steps follow:
- **Cross-check with ChEMBL.** Each resolved compound is looked up in ChEMBL by full
  InChIKey. Agreement is recorded, and a disagreement does not block.
- **Manual collapses (§5.1).** The inorganic salt collapses, such as lithium, are recorded
  manual decisions. Scaled names that would need one fall to `mixture` and are reported.

## Stage 2 — synonyms

**Sources, in order of trust:**
1. **DrugAge's own name.**
2. **ChEMBL:** the preferred name and `molecule_synonyms` (INN, USAN, BAN, trade names,
   research codes).
3. **PubChem:** the depositor synonym list, after the filters below.

**PubChem filters** are deterministic and versioned. A dropped string is recorded with
its reason, so the filters can be audited.
- **Identifiers, not names:**
  - CAS numbers, UNII, and database IDs (CHEMBL, DTXSID or DTXCID, SCHEMBL, ZINC, MFCD,
    AKOS, NSC, EINECS, Wikidata Q-numbers);
  - supplier catalogue codes (HY-, CS-, BRD-, and similar);
  - InChI and SMILES strings.
- **Grade, supplier or product strings:** strings containing *standard*, *CRS*, *USP*,
  *reference*, *analytical*, *grade*, *certified*, *for system suitability*, a
  concentration or dose, or a formulation word. Examples are "Estriol (Standard)",
  "Estriol 5.0 Cream" and "Estriol CRS".
- **Language and status brackets** ("Estriolo [Italian]", "[INN]"): the bracket is
  stripped and the name kept.
- **Short strings,** 4 characters or fewer. The resolver never auto-accepts these anyway,
  and they would only flood review.
- **Very long systematic names,** over 60 characters. They are harmless but cost time, and
  they essentially never appear in registry text.
- **Common English words:** a single-token synonym that is a dictionary word, such as
  "Thermal" or "Aid".

**Collisions.** A normalised string generated for two or more compounds, or one that
equals any string in the seed fixture (synonym, negative or review), is **removed from
automatic matching for every compound involved** and put on their review lists. It never
auto-accepts. The count is reported (step-7 secondary question).

## Stage 3 — matching and querying

**[decide] D1. Which synonyms become registry *query* strings.**
- *Proposed:* DrugAge name, ChEMBL preferred name, and ChEMBL INN, USAN, BAN and trade
  names.
- *Not:* PubChem synonyms. They are used **for matching only**.
- *Why:* PubChem synonyms as queries would multiply the fetch many times over, mostly on
  noise, and MeSH expansion makes it worse (§5.1).
- *Cost:* a trial that names a compound only by a PubChem-only synonym is found only if
  another query brings it in. That is a recall cost, already declared as an unmeasured gap
  (§10).

**[decide] D2. No fuzzy (edit-distance-1) matching for scaled compounds.**
- *Proposed:* off.
- *Why:* with tens of thousands of unreviewed synonyms, near-misses would flood review.
  Fuzzy matching can never auto-accept anyway, so precision is unaffected; the cost is
  recall only.

**[decide] D3. Scaled compounds get no `must_not_match` lists.**
- *Proposed:* the generated set has no negatives beyond the collision rule.
- *Why:* hand negatives were the seed fixture's main defence, and writing them for about
  1,000 compounds is exactly the manual work scaling avoids. This is the "dirty" half of
  the step-7 rationale, and step 7 measures what it costs.

**D4. Performance (engineering, no behaviour change).** Matching currently runs every
compound's pattern against every string. At about 50 times the compounds that is hours
per run. A **word index** will find the candidate compounds for a string before the
patterns run:
- a term can only match where its first word appears as a whole word;
- so the index is exact, not approximate.

It is proven, not argued: before any scaled compound is added, a seed-only run with the
index must produce a resolver diff of **0 changes**.

## Freeze

The step-7 frozen inputs record:
- the rules version and hash;
- the synonym table hash;
- source release dates (PubChem retrieval date, ChEMBL release);
- per-outcome counts from stage 1;
- filter drop counts per reason;
- the collision count.
