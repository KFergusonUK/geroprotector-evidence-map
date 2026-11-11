# Geroprotector Human Evidence Map — Specification

**Status:** v0.2 draft spec
**Owner:** Kevin Ferguson

**Changes since v0.1** (2026-11-11): entry criterion extended to ATC level-4 classes
(§1, §5.5); §5.4 replication rule corrected to require significant extension, with ITP
nulls as a first-class output cell; v1 headline scope limited to compounds with mammal
evidence (§1.1); `lab_group` derivation defined (§5.4); seed list revised (§6); DrugAge
licence resolved (§10). `agesdk/schema.sql` is authoritative over the table sketches in §4.

---

## 1. The question

> For compounds with demonstrated lifespan extension in any species, what human
> trial data exists, under what indications, and was it ever reported?

Deliberately **not** filtered by whether anyone has labelled the compound a
"longevity drug". A compound enters on its animal evidence and brings its entire
human trial dossier with it, whatever indication produced it.

### Entry criterion

A compound enters the map if **either**:

- **direct** — it has animal lifespan evidence (DrugAge), **or**
- **class** — it belongs to an ATC level-4 class that contains a *direct* compound.

Class entry is a weaker, transitive inference and is recorded as
`compound.entry_route = 'class'`. Every derived view must be filterable on
`entry_route`, and the two routes are **never merged in output**. See §5.5.

### Why this is worth building

Human trial data on geroprotective candidates is accumulating under unrelated
labels — diabetes, heart failure, oncology — and nobody has systematically
mapped it. SGLT2 inhibitors are the archetype: ~70,000 patients of
hard-endpoint RCT data, assembled entirely under cardiometabolic indications,
while the field writes reviews about metformin. (Only canagliflozin has animal
lifespan evidence; the other SGLT2 inhibitors enter by class — which is exactly
why class entry exists and why it must stay labelled.)

### Output

|                                            | No human trials       | Human trials exist |
| ------------------------------------------ | --------------------- | ------------------ |
| **Replicated animal evidence**             | Untested candidates   | **Gold cell**      |
| **High-quality animal null (ITP)**         | —                     | **Null cell**      |
| **Single-lab / weak animal evidence**      | Noise                 | Over-hyped         |

Three deliverables, in priority order:

1. **Gold cell** — replicated animal lifespan extension AND human trials exist.
2. **Null cell** — strong human interest AND a high-quality animal null (an ITP
   result with no significant extension). Examples: metformin, resveratrol,
   nicotinamide riboside, fisetin, alpha-ketoglutarate. This is a first-class
   deliverable, not a footnote: well-powered negative evidence alongside heavy
   human investment is a finding in its own right.
3. **Untested candidates** — what nobody has tried in humans, and why.

Each cell is produced separately for `entry_route = 'direct'` and `'class'`.

### 1.1 Scope for v1

The **headline analysis covers only compounds with mammal lifespan evidence**
(159 compounds in DrugAge Build 5, by `species_taxon.tier = 'mammal'`).

Worm, fly, yeast and all other rows are still loaded into the normalised layer.
**Tiering is a view, not a deletion.**

### Secondary question — "under-tested"

A compound is **under-tested** if it has replicated animal lifespan evidence but
**zero** registered trials carrying an ageing-adjacent endpoint. Defined
concretely so it is computable, not a judgement call:

Ageing-adjacent endpoints (ANY of):
- all-cause mortality
- incident chronic disease (CVD, cancer, CKD, dementia, T2D)
- frailty index / sarcopenia measures
- physical function (gait speed, grip strength, SPPB, 6MWT)
- cognitive function
- an explicit biological-age or epigenetic-clock measure

---

## 2. Non-goals (v1)

- No causal inference. This is a map of evidence, not an effect-size meta-analysis.
- No dose comparison across species.
- No attempt to judge whether a compound *works*.
- No scraping of anything without an API or bulk download.

---

## 3. Sources

| Source | Role | Access |
| ------ | ---- | ------ |
| **DrugAge** (HAGR) | Entry criterion: compounds with measured lifespan effects | Bulk CSV download |
| **ClinicalTrials.gov** | Human trial registry + posted results | REST API v2 |
| **PubChem** | Compound identity resolution (CID, InChIKey, synonyms) | PUG REST API |
| **ChEMBL** | Secondary identity, salt→parent hierarchy, **ATC codes (class entry)**, targets | REST API |
| **Europe PMC** | Publication linkage for trials; **authors + affiliations for `lab_group`** | REST API |
| **OpenAlex** | Bibliometrics, citation context | REST API, no key |

All six are open and free. Record the access date and API version for every fetch.

DrugAge licence: HAGR content is **CC-BY 3.0**
(<https://genomics.senescence.info/legal.html>); cite Barardo et al. (2017)
*Aging Cell* 16(3):594-597.

---

## 4. Architecture

Four layers. SQLite throughout — resist anything bigger until there is a
demonstrated reason. The full DDL lives in `agesdk/schema.sql`; the sketches
below show intent.

### 4.1 Raw layer

Store each API response **verbatim** with fetch metadata. Never overwrite;
append a new row and supersede. Sources change under you and you will want to diff.
Enforced by triggers: `raw_response` rejects UPDATE and DELETE.

```
raw_response(
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,          -- 'drugage' | 'ctgov' | 'pubchem' | ...
  endpoint TEXT NOT NULL,        -- URL path, or 'dataset.zip!member' for archives
  request_params TEXT NOT NULL,  -- canonical JSON
  response_body TEXT NOT NULL,   -- JSON or CSV as returned
  http_status INTEGER,
  fetched_at TEXT NOT NULL,      -- ISO 8601 UTC
  api_version TEXT,
  content_sha256 TEXT NOT NULL,  -- idempotency: identical content is not re-stored
  response_meta TEXT             -- JSON: headers, archive hash, licence, ...
)
```

`v_raw_current` gives the latest row per (source, endpoint, request_params).

### 4.2 Normalised layer

One table per entity. Every compound resolved to a canonical identity.

```
compound(
  compound_id INTEGER PRIMARY KEY,
  canonical_name TEXT NOT NULL,
  pubchem_cid INTEGER,           -- nullable: some will not resolve
  inchikey TEXT,                 -- full 27 chars, enforced (see §5.1)
  chembl_id TEXT,
  is_mixture BOOLEAN DEFAULT 0,
  entry_route TEXT NOT NULL,     -- 'direct' | 'class'  (§1, §5.5)
  notes TEXT
)

compound_component(mixture_id, component_id)   -- mixtures → parents

compound_synonym(compound_id, synonym, source)

compound_atc(                    -- many-to-many; aspirin is in B01AC and N02BA
  compound_id INTEGER NOT NULL,
  atc_code TEXT NOT NULL,        -- level 5, e.g. 'A10BK02'
  atc_level4 TEXT,               -- generated: 'A10BK'
  source TEXT DEFAULT 'chembl',
  review_status TEXT NOT NULL,   -- 'auto' | 'pending_review' | 'accepted' | 'rejected'
  reviewed_by TEXT, reviewed_at TEXT, note TEXT
)

species_taxon(species, tier)     -- tier: mammal | other_vertebrate | invertebrate | fungus | other

animal_evidence(
  id INTEGER PRIMARY KEY,
  compound_id INTEGER NOT NULL,
  species TEXT NOT NULL,
  strain TEXT,
  sex TEXT,                      -- 'M' | 'F' | 'both' | 'hermaphrodite' | 'unknown'
  dosage, age_at_initiation, treatment_duration TEXT,
  avg_lifespan_change_pct REAL, avg_lifespan_significance TEXT,   -- 'S' | 'NS' | NULL
  max_lifespan_change_pct REAL, max_lifespan_significance TEXT,
  is_itp BOOLEAN,
  pmid TEXT,
  source TEXT NOT NULL DEFAULT 'drugage',
  source_compound_name TEXT NOT NULL,   -- verbatim
  raw_response_id, source_row_number    -- provenance + idempotency
)

publication(pmid, title, journal, pub_year,
            senior_author, senior_author_orcid, senior_affiliation,
            lab_group, lab_group_method)          -- 'derived' | 'manual'
publication_author(pmid, position, full_name, orcid, affiliation)

trial(
  nct_id TEXT PRIMARY KEY,
  title, phase, status TEXT,
  enrollment INTEGER,
  start_date, completion_date, primary_completion_date TEXT,
  sponsor, sponsor_class TEXT,
  results_state TEXT NOT NULL,   -- see §5.2 — NOT a boolean; enum enforced
  results_posted_date TEXT
)

trial_intervention(nct_id, raw_name, intervention_type, compound_id)
trial_condition(nct_id, condition_text, mesh_term)
trial_outcome(id, nct_id, outcome_type, measure, time_frame,
              ageing_adjacent, ageing_category, classifier_version)
```

### 4.3 Crosswalk layer

**The hard part of this project.** Keep mappings as *data*, in version control,
separate from code, each with provenance and confidence.

```
crosswalk(
  id INTEGER PRIMARY KEY,
  from_source TEXT NOT NULL,
  from_value TEXT NOT NULL,      -- e.g. 'Rapamune 2mg tablet'
  compound_id INTEGER NOT NULL,
  method TEXT NOT NULL,          -- 'exact' | 'synonym' | 'fuzzy' | 'manual'
  confidence REAL NOT NULL,      -- 0.0–1.0
  reviewed_by TEXT,              -- REQUIRED (enforced) when method is fuzzy or manual
  reviewed_at TEXT,
  note TEXT
)
```

Manual decisions are first-class citizens here. Export this table to CSV in the
repo so review history is diffable.

### 4.4 Derived layer

Views only. Nothing here is a source of truth. **Every compound-level view
carries `entry_route`**, and output is produced per route, never pooled.

- `v_compound_summary` — animal evidence strength + human trial counts
- `v_gold_cell` — replicated animal extension AND human trials exist
- `v_null_cell` — ITP null AND human trials exist (§1, §5.4)
- `v_under_tested` — replicated animal evidence AND zero ageing-adjacent endpoints
- `v_unreported` — completed trials, results never posted or published
- `v_class_entry_basis` — for each compound, which direct compound and ATC class justify class entry
- `v_atc_review_needed` — ATC rows awaiting a human decision (§5.5)
- `v_entry_route_check` — stored `entry_route` disagreeing with the data (should be empty)
- `v_replication_overlap` — replication claims resting on shared authorship (§5.4)

---

## 5. Hard problems — design these before coding

### 5.1 Compound identity resolution

The same molecule appears as: `rapamycin`, `sirolimus`, `Rapamune`,
`AY-22989`, `RAPA`, `Sirolimus 0.5 mg`, `everolimus` (different molecule — must
NOT match).

Resolution pipeline, in order, stopping at first confident hit:
1. Exact match against `compound_synonym`
2. PubChem synonym lookup → CID → InChIKey
3. Normalised string match (lowercase, Unicode-normalise hyphens, strip dose/formulation/salt tokens)
4. Fuzzy match → **queue for manual review, never auto-accept**

Salt forms (hydrochloride, sodium, etc.) collapse to parent compound; record
the salt in a note. Mixtures get `is_mixture = 1` and link to multiple parents
via `compound_component`.

**Identity is the full 27-character InChIKey.** The first 14-character block
encodes connectivity without stereochemistry: 17α- and 17β-estradiol share it,
as do NDGA and masoprocol, and trans- and cis-resveratrol. The schema rejects
truncated keys.

PubChem's parent-compound lookup is not reliable for inorganic salts (lithium
carbonate → carbonic acid). Such collapses are manual decisions.

**Rule: no fuzzy match enters `trial_intervention.compound_id` without human review.**
Precision over recall. A false join poisons every downstream count.

### 5.2 `results_state` is not a boolean

Model as an enum from the start:

- `POSTED` — results posted on ClinicalTrials.gov
- `PARTIAL` — some outcome measures posted, others not
- `PUBLISHED_ONLY` — no registry results, but a linked publication exists
- `NOT_POSTED_DUE` — completed > 12 months ago, nothing posted
- `NOT_POSTED_NOT_DUE` — completed recently, within posting window
- `TERMINATED_NO_RESULTS` — stopped early, nothing posted
- `WITHDRAWN` — never enrolled
- `ONGOING` — not yet complete
- `UNKNOWN` — status stale, registry not updated

The publication-bias finding lives in the distinction between `NOT_POSTED_DUE`
and `TERMINATED_NO_RESULTS`. Collapsing these to a boolean destroys the result.

### 5.3 Ageing-adjacent endpoint classification

Outcome measure strings are free text. Classify with:
1. A keyword/regex rule set, versioned in the repo as YAML
2. Manual review of anything ambiguous
3. Store the rule set version against each classification (`trial_outcome.classifier_version`)

Do **not** use an LLM call as an unreviewed classifier in the pipeline — it is
not reproducible and the whole point is a defensible map.

### 5.4 Replication detection

"Replicated animal evidence" means significant lifespan **extension**, shown by:
- ≥2 independent lab groups, OR
- ≥1 ITP (Interventions Testing Program) result showing **significant lifespan extension**

ITP results are the gold standard — multi-site by design. Flag them explicitly;
they should carry more weight than any single-lab finding.

**ITP nulls are evidence, not absence of evidence.** An ITP result with no
significant extension is high-quality negative evidence. It does not count
toward replication, and it places the compound in the **null cell** (§1) when
human trials exist. A compound can have both an ITP null and non-ITP positive
results (alpha-ketoglutarate); report both, do not net them out.

Record sex-specific effects separately. Several compounds (canagliflozin,
17-α-estradiol) extend male lifespan only — collapsing sexes loses a real signal.

**`lab_group` derivation.** For each PMID behind an animal result, fetch the
author list from Europe PMC. `lab_group` = **senior (last) author + their
affiliation**, normalised. Do not treat any shared author as a shared group
(large consortia would merge everything); manual overrides are allowed and
recorded (`lab_group_method = 'manual'`).

**Overlap flag.** Where "≥2 independent lab groups" is satisfied only by
publications whose author lists overlap (any shared author, matched by ORCID
where available, else normalised name), flag the replication as resting on
overlapping authorship rather than independent groups (`v_replication_overlap`).
Flagged replication is reported separately from clean replication.

### 5.5 Class entry via ATC

- ATC codes are sourced from **ChEMBL** (`molecule.atc_classifications`), stored in
  `compound_atc` with provenance. A compound with no ATC code has no class.
- Class membership is at **ATC level 4** (5 characters, e.g. `A10BK` SGLT2 inhibitors).
- **One hop only.** A compound enters by class only through a class containing a
  `direct` compound with animal evidence. A class-entered compound's own other
  classes never propagate further.
- **Multi-class compounds are flagged for manual review** (`v_atc_review_needed`).
  Their ATC rows start `pending_review` and carry no class entry until a reviewer
  marks each `accepted` or `rejected`. Example: aspirin is in B01AC (platelet
  aggregation inhibitors) and N02BA (salicylic acid derivatives), and propagating
  through both would pull in clopidogrel and salsalate on the strength of one ITP cohort.
- "Other" buckets (level-4 codes ending in `X`, e.g. `A16AX`) group unrelated
  drugs. They are also flagged and start `pending_review`.
- Single, specific classes are `auto` and carry class entry without review.
- Class-entered compounds never appear in direct-entry output, and vice versa.

---

## 6. Seed list (n=18 + 2 class test cases)

Chosen to stress the matching logic, not for fame. Resolve all by hand first;
they are the test fixture for the resolver: `data/fixtures/seed_compounds.yaml`.

**Naming nightmares**
- rapamycin / sirolimus
- 17-α-estradiol
- nordihydroguaiaretic acid (NDGA)
- alpha-ketoglutarate

**Heavy human data under other indications** *(the gold cell candidates)*
- metformin
- canagliflozin
- aspirin
- lithium
- acarbose
- captopril
- meclizine

**Senolytics**
- quercetin
- fisetin

**Supplement-adjacent — expect messy, low-quality trials**
- nicotinamide mononucleotide (NMN)
- nicotinamide riboside
- resveratrol
- spermidine
- taurine

**Class-layer test cases (not seeds; not in DrugAge)**
- empagliflozin — must enter by class via A10BK (canagliflozin is direct)
- semaglutide — must **not** enter: no GLP-1 receptor agonist is in DrugAge,
  so A10BJ has no direct basis, despite an enormous human dossier

**Excluded under the mixture rule:** dasatinib + quercetin, glycine + NAC.
Neither combination is in DrugAge as such; trial strings naming them go to
manual review and never silently map to a component.

---

## 7. Build order

1. **Resolve the seed compounds by hand.** Build the fixture first.
2. ClinicalTrials.gov client → raw layer, for the seed compounds only.
3. Intervention string resolver → measure precision/recall against the fixture.
4. **Decision point:** if matching is too noisy at seed scale, stop and rethink
   before scaling. Cheap failure is the point of this step.
5. `results_state` derivation.
6. Endpoint classifier + rule set.
7. Scale to full DrugAge compound list (all species loaded; mammal tier for headline).
8. ChEMBL ATC load, class entry, `lab_group` derivation.
9. Derived views, then the output table.

---

## 8. Engineering notes

- **Rate limiting** on every client. Be a good citizen; these are free public APIs.
- **Cache aggressively.** Raw layer *is* the cache — never re-fetch what you have.
- **Idempotent fetchers.** Re-running must not duplicate rows.
- **Tests on the resolver specifically.** It is where correctness actually matters.
- Keep secrets out; none of these APIs need a key, which is deliberate.

---

## 9. Publication

Publish open from the start — the **dataset is more valuable than the analysis**.

- Code: MIT or Apache 2.0
- Derived dataset: CC-BY, versioned releases, DOI via Zenodo
- Document every source's own licence and attribution requirements
- Crosswalk table published as CSV so others can audit and correct the joins

Explicit aim: make this useful enough that an academic group wants to
collaborate. That is the realistic route to the data behind governance walls
(SDE / OpenSAFELY), which a solo developer cannot reach alone.

---

## 10. Open questions

- ~~Does DrugAge's licence permit redistribution of derived data?~~ **Resolved:**
  CC-BY 3.0, redistribution permitted with attribution.
- DrugAge includes lifespan-*shortening* results (e.g. diethylnitrosamine in
  hamsters). Should direct entry require at least one positive result, or any
  measured effect? Affects the 159-compound headline count.
- Is the EU Clinical Trials Register (or WHO ICTRP) worth adding in v2 for non-US coverage?
- How to handle trials where the compound is a comparator or background therapy
  rather than the intervention? (ClinicalTrials.gov arm groups carry arm type.)
- Should observational studies (not just RCTs) be in scope? Probably v2.
