# Geroprotector Human Evidence Map — Specification

**Status:** v0.3 draft spec
**Owner:** Kevin Ferguson

**Changes since v0.2** (2026-11-11):
- Direction of effect is first-class (`animal_evidence.direction`); every row is kept.
- Entry is now **two co-equal paths**: extension (conservative) and harm (sensitive,
  mandatory human review). Their counts are never merged (§1, §5.4, §5.7).
- ITP evidence recorded as cohorts positive / cohorts tested, by sex, against a
  documented threshold held as data (§5.4).
- Residual ATC classes (…X) never carry class entry (§5.5).
- New systemic exposure criterion for interventions (§5.6).
- Fixture decisions: NDGA/masoprocol linked not merged; lithium manual salt collapse;
  acarbose and NMN deferred to ChEMBL; aluminium acetylsalicylate unresolvable (§5.1, §6).

`agesdk/schema.sql` is authoritative over the table sketches in §4.

---

## 1. The question

> For compounds with measured effects on animal lifespan, what human trial data
> exists, under what indications, and was it ever reported?

Deliberately **not** filtered by whether anyone has labelled the compound a
"longevity drug". A compound enters on its animal evidence and brings its entire
human trial dossier with it, whatever indication produced it.

### Two entry paths, co-equal outputs

Lifespan effects run both ways, and both matter. The map has two entry paths.
They are separate deliverables of equal standing. **No view, table or headline
figure ever merges their counts**: a compound on both paths (metformin, aspirin,
canagliflozin, quercetin) appears in both outputs, counted separately in each.

| | **Extension path** | **Harm path** |
|---|---|---|
| Question | Which compounds extend animal lifespan, and what human data exists? | Which compounds shorten mammalian lifespan while having substantial human exposure? |
| Enters on | ≥1 animal result with significant lifespan **extension** (any species) | ≥1 **mammalian** result with significant lifespan **shortening** |
| Threshold | **Conservative.** Replication matters; tiers by species and replication | **Sensitive.** A single credible mammalian signal surfaces a candidate: missing one costs more than a false alarm |
| Review | Automated, from documented thresholds | **Mandatory human review.** Nothing reaches the output automatically, ever (§5.7) |
| Class entry (ATC) | Yes, one hop, labelled `entry_route = 'class'` (§5.5) | No: direct evidence only |
| Deliverable | Gold cell, null cell, untested candidates | `v_harm_signal` |

A compound in DrugAge with neither significant extension nor significant mammalian
shortening (e.g. NMN: one fly study, not significant) stays in the data and is on
no path.

### Extension path: class entry

A compound also enters the extension path if it belongs to an ATC level-4 class
containing a compound with direct extension evidence. This is a weaker, transitive
inference, recorded as `compound.entry_route = 'class'`. Every derived view is
filterable on `entry_route`, and the two routes are **never merged in output**.
See §5.5.

### Why this is worth building

Human trial data on geroprotective candidates is accumulating under unrelated
labels — diabetes, heart failure, oncology — and nobody has systematically
mapped it. SGLT2 inhibitors are the archetype: ~70,000 patients of
hard-endpoint RCT data, assembled entirely under cardiometabolic indications,
while the field writes reviews about metformin. (Only canagliflozin has animal
lifespan evidence; the other SGLT2 inhibitors enter by class — which is exactly
why class entry exists and why it must stay labelled.)

The harm path is the mirror image: a drug in wide human use that shortens
mammalian lifespan in a credible study is worth knowing about, whatever its
indication.

### Outputs

**Extension path**

|                                            | No human trials       | Human trials exist |
| ------------------------------------------ | --------------------- | ------------------ |
| **Replicated animal extension**            | Untested candidates   | **Gold cell**      |
| **High-quality animal null (ITP)**         | —                     | **Null cell**      |
| **Single-lab / weak animal extension**     | Noise                 | Over-hyped         |

**Harm path**

| | Substantial human exposure |
|---|---|
| **Credible mammalian lifespan shortening, human-reviewed** | **Harm signal** (`v_harm_signal`) |

Deliverables, all first-class:

1. **Gold cell** — replicated animal extension AND human trials exist.
2. **Null cell** — strong human interest AND a high-quality animal null (ITP cohorts
   below the ITP threshold). Examples: metformin (0/2), resveratrol (0/6), nicotinamide
   riboside (0/2), fisetin (0/4), alpha-ketoglutarate (0/2).
3. **Harm signal** — shortens mammalian lifespan AND widely used in humans, after
   mandatory human review.
4. **Untested candidates** — replicated extension that nobody has tried in humans, and why.

Each extension-path cell is produced separately for `entry_route = 'direct'` and `'class'`.

### 1.1 Scope for v1

The headline universe is the **159 compounds with any mammal evidence** in DrugAge
Build 5 (`species_taxon.tier = 'mammal'`). Within it (as of 2026-11-11):

- **78** have significant mammal **extension**: the extension-path headline.
- **20** have significant mammal **shortening**: harm-path candidates (11 of them are
  also on the extension path).
- The remainder have only null or unassessed mammal results; those with ITP data
  feed the null cell.

Worm, fly, yeast and all other rows are loaded into the normalised layer
regardless. **Tiering is a view, not a deletion.**

### Secondary question — "under-tested"

A compound is **under-tested** if it has replicated animal lifespan extension but
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
- No attempt to judge whether a compound *works* — or is *safe*. The harm signal is
  a pointer to evidence that deserves attention, not a toxicity verdict.
- No scraping of anything without an API or bulk download.

---

## 3. Sources

| Source | Role | Access |
| ------ | ---- | ------ |
| **DrugAge** (HAGR) | Entry: compounds with measured lifespan effects, both directions | Bulk CSV download |
| **ClinicalTrials.gov** | Human trial registry + posted results | REST API v2 |
| **PubChem** | Compound identity resolution (CID, InChIKey, synonyms) | PUG REST API |
| **ChEMBL** | Secondary identity, salt→parent hierarchy, **ATC codes (class entry)**, approval status, targets | REST API |
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
compound_relation(compound_id, related_compound_id,
                  relation,      -- 'same_substance_as'; reviewer required (§5.1)
                  reviewed_by, reviewed_at, note)

compound_synonym(compound_id, synonym, source)

compound_atc(                    -- many-to-many; aspirin is in B01AC and N02BA
  compound_id INTEGER NOT NULL,
  atc_code TEXT NOT NULL,        -- level 5, e.g. 'A10BK02'
  atc_level4 TEXT,               -- generated: 'A10BK'
  source TEXT DEFAULT 'chembl',
  review_status TEXT NOT NULL,   -- 'auto' | 'pending_review' | 'accepted' | 'rejected' | 'residual'
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
  direction TEXT NOT NULL,       -- 'extension' | 'shortening' | 'null' | 'unassessed' (§5.4)
  direction_basis TEXT NOT NULL, -- 'avg' | 'max' | 'none'
  direction_rule_version TEXT NOT NULL,
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

analysis_threshold(name, value, rationale)        -- documented thresholds views apply

harm_review(                     -- the ONLY route into v_harm_signal (§5.7)
  compound_id INTEGER PRIMARY KEY,
  decision TEXT NOT NULL,        -- 'surface' | 'reject'
  human_exposure_basis TEXT,     -- required to surface
  rationale TEXT NOT NULL,
  reviewed_by TEXT NOT NULL,     -- a named human; 'auto'/'system'/'pipeline' rejected
  reviewed_at TEXT NOT NULL,
  evidence_row_ids TEXT NOT NULL -- JSON array: the animal_evidence rows reviewed
)

trial(
  nct_id TEXT PRIMARY KEY,
  title, phase, status TEXT,
  enrollment INTEGER,
  start_date, completion_date, primary_completion_date TEXT,
  sponsor, sponsor_class TEXT,
  results_state TEXT NOT NULL,   -- see §5.2 — NOT a boolean; enum enforced
  results_posted_date TEXT
)

trial_intervention(nct_id, raw_name, intervention_type, compound_id,
                   route, systemic_exposure,      -- 'systemic' | 'local' | 'unclear' (§5.6)
                   route_rule_version)
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
carries `entry_route`**, output is produced per route, and **no view combines
extension-path and harm-path counts**.

Built:
- `v_itp_summary` — ITP cohorts positive / tested, overall and by sex, vs threshold
- `v_extension_evidence` — extension-path evidence: extension rows only, lab groups, ITP ratio, replication
- `v_itp_null` — ITP-tested compounds below the ITP threshold (null-cell evidence)
- `v_harm_candidates` — harm-path review queue (detection only; surfaces nothing)
- `v_harm_signal` — harm-path deliverable; reads only reviewed `surface` decisions
- `v_class_entry_basis` — which direct compound and ATC class justify each class entry
- `v_atc_review_needed` — multi-class compounds awaiting an ATC decision (§5.5)
- `v_entry_route_check` — stored `entry_route` disagreeing with the data (should be empty)

To build once trials are loaded:
- `v_gold_cell`, `v_null_cell`, `v_under_tested`, `v_unreported`, `v_compound_summary`
- `v_replication_overlap` — replication resting on shared authorship (§5.4)

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

**Linked, not merged.** Where two records are plausibly the same substance but
have different full InChIKeys (NDGA, stereo undefined; masoprocol, the meso form),
they are **separate compound rows** joined by a reviewed `same_substance_as` link
in `compound_relation`. The canonical InChIKey is never overridden to force a
merge, and the link never merges counts.

**Manual salt-collapse overrides.** PubChem's parent-compound lookup is not
reliable for inorganic salts (lithium carbonate → carbonic acid; lithium chloride →
no parent). Where it fails, the collapse is a recorded manual decision.
Current overrides:

| Compound | Canonical identity | Salts collapsed | Decided |
|---|---|---|---|
| lithium | Li⁺ (CID 28486, HBBGRARXTFLTSG-UHFFFAOYSA-N) | carbonate, chloride, citrate; orotate/aspartate to review | Kevin Ferguson, 2026-11-11 |

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

### 5.4 Direction of effect, extension path, replication

**Direction.** Every animal result carries a direction, derived from the source's
significance flags (`agesdk/evidence.py`, rule `direction-v1`), never from effect
size alone:

1. Average lifespan significant, with a value → sign of the average change
2. Otherwise max lifespan significant, with a value → sign of the max change
3. Otherwise any measure reported not significant → `null`
4. Otherwise (no significance reported, or a flag with no value) → `unassessed`

`null` means *measured and not significant*. `unassessed` means *significance not
reported* and is **not** negative evidence: it never feeds the null cell. A
significant change of exactly 0 is `null`. All rows are kept, whatever their direction.

In DrugAge Build 5: 1,673 extension, 399 shortening, 1,130 null, 221 unassessed rows.

**Extension-path entry** requires ≥1 result with significant lifespan **extension**.
"Measured lifespan effect" was underspecified and admitted diethylnitrosamine, a
carcinogen; shortening and null results never qualify a compound for this path
and never carry class entry.

**Replicated** extension means either:
- ≥ `replication_min_lab_groups` (2) independent lab groups with significant extension, OR
- the compound meets the **ITP threshold**.

**ITP evidence is a ratio, not a boolean.** For each compound the map reports
`itp_cohorts_positive / itp_cohorts_total`, overall and separately for males and
females. A cohort is one ITP result row in the source (one sex × one dose/start
age × one study); a positive cohort is one with `direction = 'extension'`. Views
apply a documented threshold held in `analysis_threshold`:

- `itp_min_positive_cohorts` = 1
- `itp_min_positive_fraction` = 0.0

The threshold is applied by the views, not by anyone judging individual compounds,
and the ratio is always shown beside it. Aspirin reads 1/6 (male 1/3, female 0/3);
rapamycin 14/16 (male 7/8, female 7/8); canagliflozin 3/6 (male 3/3, female 0/3).
The reader sees the difference; changing the threshold is a one-row data change.

**ITP nulls are evidence, not absence of evidence.** ITP-tested compounds below
the threshold form the **null cell** when human trials exist. A compound can have
an ITP null and non-ITP positive results (alpha-ketoglutarate); report both, do not
net them out.

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
- Class entry applies to the **extension path only**, and only from a basis compound
  with significant extension evidence.
- **One hop only.** A class-entered compound's own other classes never propagate further.
- **Multi-class compounds are flagged for manual review** (`v_atc_review_needed`).
  Their ATC rows start `pending_review` and carry no class entry until a reviewer
  marks each `accepted` or `rejected`. Example: aspirin is in B01AC (platelet
  aggregation inhibitors) and N02BA (salicylic acid derivatives).
- **Residual classes never carry class entry.** Level-4 codes ending in `X`
  ("other …", e.g. `A16AX`) are groupings of convenience, not mechanisms. They are
  stored with `review_status = 'residual'` (enforced for exactly those codes), do not
  count toward multi-class, and cannot be accepted by review.
- Single, specific classes are `auto` and carry class entry without review.
- Class-entered compounds never appear in direct-entry output, and vice versa.

### 5.6 Systemic exposure criterion

An intervention qualifies only if it **plausibly produces systemic exposure** to
the compound. Identity and route are separate questions: a sirolimus-eluting stent
*is* sirolimus, and resolves to it, but the trial does not count as human sirolimus
data for this map.

- Stated as a rule, applied uniformly — not decided case by case.
- **Qualifies (systemic):** oral, IV, IM, SC, transdermal systems designed for
  systemic delivery, inhaled where systemic absorption is the intent.
- **Excluded (local):** drug-eluting stents and balloons, topicals for local effect,
  intravitreal and other intraocular injections, intra-articular injections, local
  implants, mouthwashes, eye drops.
- **Unclear** → manual review (e.g. high-dose topical with known systemic absorption).
- Recorded per intervention: `trial_intervention.route`, `systemic_exposure`
  (`systemic` | `local` | `unclear`), and the `route_rule_version` that produced it.
  Only `systemic` interventions count in any output.

Known consequences: 17-α-estradiol's human use is topical alfatradiol (alopecia), and
masoprocol's is a topical cream; neither is expected to contribute qualifying trials.

### 5.7 Harm path

**Entry (sensitive).** A compound is a harm candidate when it has ≥
`harm_min_mammal_shortening_rows` (1) mammalian result with significant lifespan
shortening. Invertebrate shortening does not qualify. Unassessed results do not
qualify, but are visible to the reviewer.

**Mandatory manual review.** No compound enters `v_harm_signal` automatically,
ever, whatever the evidence. Enforced in the schema, as the crosswalk reviewer
rule is:

- `v_harm_signal` reads **only** from `harm_review` rows with `decision = 'surface'`.
- `harm_review` cannot hold a row without a named reviewer (not empty, not
  `auto`/`system`/`pipeline`/`script`), a review date, a rationale, and the list of
  evidence rows reviewed.
- Surfacing additionally requires a stated **human exposure basis**: why exposure is
  substantial (approved drug in wide use, common supplement, dietary or occupational
  exposure).
- `v_harm_candidates` is the review queue. Appearing in it surfaces nothing.
- If evidence changes after review (rows added or withdrawn), `v_harm_signal` flags
  `evidence_changed_since_review` and `still_meets_threshold`; the decision is
  revisited, not silently kept.

A false positive here does real damage. The harm signal is a pointer to published
animal evidence that deserves attention, never a claim that a drug is unsafe in
humans.

**Never merged.** A compound on both paths is reported in both, with each path's
counts computed from its own direction only.

---

## 6. Seed list (n=18 + 2 class test cases + 1 linked compound)

Chosen to stress the matching logic, not for fame. Resolve all by hand first;
they are the test fixture for the resolver: `data/fixtures/seed_compounds.yaml`.

**Naming nightmares**
- rapamycin / sirolimus
- 17-α-estradiol
- nordihydroguaiaretic acid (NDGA) — with **masoprocol** as a separate, linked row
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
- nicotinamide mononucleotide (NMN) — on no path: no significant extension in DrugAge
- nicotinamide riboside
- resveratrol
- spermidine
- taurine

**On both paths (extension and harm candidate):** metformin, canagliflozin,
aspirin, quercetin.

**Class-layer test cases (not seeds; not in DrugAge)**
- empagliflozin — must enter by class via A10BK (canagliflozin is direct)
- semaglutide — must **not** enter: no GLP-1 receptor agonist is in DrugAge,
  so A10BJ has no direct basis, despite an enormous human dossier

**Excluded under the mixture rule:** dasatinib + quercetin, glycine + NAC.
Neither combination is in DrugAge as such; trial strings naming them go to
manual review and never silently map to a component.

**Pending ChEMBL (deferred decisions):** acarbose — take the record carrying ATC
A10BF01; NMN — take the β-anomer. **Unresolvable:** aluminium acetylsalicylate.

---

## 7. Build order

1. **Resolve the seed compounds by hand.** Build the fixture first.
2. ClinicalTrials.gov client → raw layer, for the seed compounds only.
3. Intervention string resolver → measure precision/recall against the fixture.
4. **Decision point:** if matching is too noisy at seed scale, stop and rethink
   before scaling. Cheap failure is the point of this step.
5. `results_state` derivation; systemic exposure classification (§5.6).
6. Endpoint classifier + rule set.
7. Scale to full DrugAge compound list (all species and directions loaded).
8. ChEMBL ATC load, class entry, `lab_group` derivation.
9. Derived views, then the extension-path table and the harm-path review.

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
- Harm-path outputs are published with their review records (reviewer, date,
  rationale, exposure basis, evidence rows) and the non-verdict wording of §5.7

Explicit aim: make this useful enough that an academic group wants to
collaborate. That is the realistic route to the data behind governance walls
(SDE / OpenSAFELY), which a solo developer cannot reach alone.

---

## 10. Open questions

- ~~Does DrugAge's licence permit redistribution of derived data?~~ **Resolved:**
  CC-BY 3.0, redistribution permitted with attribution.
- ~~Should direct entry require a positive result, or any measured effect?~~
  **Resolved:** direction is first-class; two entry paths (§1, §5.4, §5.7).
- **The fourth output cell — shortens animal lifespan + widely used in humans — is
  now in scope via the harm path, not deferred.**
- Is the EU Clinical Trials Register (or WHO ICTRP) worth adding in v2 for non-US coverage?
- How to handle trials where the compound is a comparator or background therapy
  rather than the intervention? (ClinicalTrials.gov arm groups carry arm type.)
- Should observational studies (not just RCTs) be in scope? Probably v2.
- What evidence establishes "substantial human exposure" for the harm path beyond
  reviewer judgement (e.g. ChEMBL approval status, prescription volume)?
