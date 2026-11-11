# Geroprotector Human Evidence Map — Specification

**Status:** v0.6 draft spec
**Owner:** Kevin Ferguson

**Changes since v0.5** (2026-11-11):
- ITP **strong** tier now requires positive cohorts in ≥2 independent experiments; the two
  sexes of one experiment read mixed (§5.4).
- **Replication** requires two (mammal) lab groups or a **strong** ITP tier; one positive
  cohort is a single result (§5.4, §11.2).
- Reviewed corrections live in `data/reviews/direction_reviews.yaml`. Two DrugAge source
  errors corrected (meclizine, Protandim) after a check of all ITP rows against primary
  sources (`docs/drugage_itp_audit.md`).
- Pipeline state saved as dated releases, pruned to the newest 12 plus monthly (§11.5).
- Refresh workflow is **manual-only** until trial normalisation exists (§11.5).
- Y-27632 / "Ximelegatran" added to the fixture as an identity trap.

**Changes in v0.5** (2026-11-11):
- New §11: refresh and change detection as a diff — source refresh with change detection,
  snapshot history, `v_cell_transitions`, literature curation queue, GitHub Action,
  and the guard that a refresh never silently changes a reviewed decision.
- Derived cells built: gold, untested candidates, under-tested, null, unreported.

**Changes in v0.4** (2026-11-11):
- `compound.evidence_tier` (measured_lifespan | inherited_class | mechanistic_only) is the
  evidential grade; `entry_route` stays the mechanism of entry. Every compound-level view
  carries the tier (§1, §4.4).
- Third entry path: chemical reprogramming cocktail components, recorded to DrugAge's
  standard and reported only in `v_mechanistic_human_dossier`, never the gold cell (§5.8).
- Direction rule v2: direction per measure; where average and maximum point opposite ways
  the row is a `conflict` for human review, not resolved by precedence (§5.4).
- ITP unit corrected from arms to **cohorts** (one sex in one independent experiment), with
  strong / mixed / weak tiers (§5.4). Cohort duplication checked (§5.4).
- Harm review sees ATC class-mates (`v_harm_review_context`); entry stays direct (§5.7).
- Reviewed source-error corrections; exact duplicate source rows counted once (§5.4).

**Changes in v0.3** (2026-11-11):
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

### Entry paths and evidence tiers

Lifespan effects run both ways, and both matter. The map has two co-equal lifespan
paths and a third, explicitly weaker, mechanistic path. They are separate deliverables.
**No view, table or headline figure ever merges their counts**: a compound on both
lifespan paths (metformin, aspirin, canagliflozin, quercetin) appears in both outputs,
counted separately in each.

| | **Extension path** | **Harm path** | **Mechanistic path** |
|---|---|---|---|
| Question | Which compounds extend animal lifespan, and what human data exists? | Which compounds shorten mammalian lifespan while having substantial human exposure? | What human data exists for named components of chemical reprogramming cocktails? |
| Enters on | ≥1 animal result with significant lifespan **extension** (any species) | ≥1 **mammalian** result with significant lifespan **shortening** | Named component of a **published chemical reprogramming cocktail**, cited (§5.8) |
| Threshold | **Conservative.** Replication matters; tiers by species and replication | **Sensitive.** A single credible mammalian signal surfaces a candidate | **Tight.** Not "regenerative medicine" broadly |
| Review | Automated, from documented thresholds | **Mandatory human review**, enforced in the schema (§5.7) | Curated to DrugAge's standard, enforced in the schema (§5.8) |
| Class entry (ATC) | Yes, one hop, labelled (§5.5) | No; class-mates shown to the reviewer as context | No |
| Deliverable | Gold cell, null cell, untested candidates | `v_harm_signal` | `v_mechanistic_human_dossier` — never the gold cell |

**Evidence tier** (`compound.evidence_tier`) is the evidential grade, distinct from
the mechanism of entry (`entry_route`):

| `evidence_tier` | `entry_route` | Premise |
|---|---|---|
| `measured_lifespan` | `direct` | The compound's own lifespan measured in animals (DrugAge) |
| `inherited_class` | `class` | Shares a specific ATC class with a compound that extends lifespan |
| `mechanistic_only` | `reprogramming_cocktail` | Component of a chemical reprogramming cocktail; no lifespan evidence |

The pairing is enforced. Where a compound qualifies several ways the strongest grade
wins (valproic acid is in DrugAge, so it is `measured_lifespan` even though it is also a
cocktail component). **Every compound-level view carries `evidence_tier`**, and no view
shows a `mechanistic_only` compound in a count without the label; a test enforces this
across all views.

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
   below the ITP threshold). Examples (cohorts positive / tested): metformin (0/2),
   resveratrol (0/4), nicotinamide riboside (0/2), fisetin (0/2), alpha-ketoglutarate (0/2).
3. **Harm signal** — shortens mammalian lifespan AND widely used in humans, after
   mandatory human review.
4. **Untested candidates** — replicated extension that nobody has tried in humans, and why.
5. **Mechanistic human dossier** — human trial data for chemical reprogramming components,
   labelled throughout as resting on a mechanistic premise, not lifespan evidence.

Each extension-path cell is produced separately for `entry_route = 'direct'` and `'class'`.

### 1.1 Scope for v1

The headline universe is the **159 compounds with any mammal evidence** in DrugAge
Build 5 (`species_taxon.tier = 'mammal'`). Within it (as of 2026-11-11):

- **77** have significant mammal **extension**: the extension-path headline.
- **19** have significant mammal **shortening**: harm-path candidates (10 of them are
  also on the extension path).
- **4** mammal results are direction conflicts awaiting review (levodopa, epitalon,
  β-aminopropionitrile ×2); they count toward no path until resolved.
- The remainder have only null or unassessed mammal results; those with ITP data
  feed the null cell.

The mechanistic path sits outside this universe by definition: its compounds have no
lifespan evidence.

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
  entry_route TEXT NOT NULL,     -- 'direct' | 'class' | 'reprogramming_cocktail'  (§1)
  evidence_tier TEXT NOT NULL,   -- 'measured_lifespan' | 'inherited_class' | 'mechanistic_only'
  notes TEXT
)

reprogramming_evidence(          -- §5.8; no bare names, enforced
  compound_id, source_component_name,
  citation_pmid, citation_doi,   -- at least one, format-checked
  cocktail_name, cocktail_components,   -- JSON array, ≥2 components
  composition_complete,
  cell_type, cell_species, in_vivo,
  demonstration_kind,            -- full_pluripotency | partial_reprogramming_rejuvenation | transdifferentiation
  demonstrated,                  -- what was actually shown (≥40 chars)
  verified_from,                 -- full_text | abstract
  recorded_by, recorded_at, reviewed_by, reviewed_at, note
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
  avg_direction, max_direction TEXT NOT NULL,  -- per measure: extension | shortening | null | unassessed
  direction TEXT NOT NULL,       -- combined, + 'conflict' (§5.4)
  direction_conflict BOOLEAN,    -- = (direction = 'conflict'), enforced
  direction_rule_version TEXT NOT NULL,
  evidence_key TEXT NOT NULL,    -- stable content hash; reviews attach to this
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

direction_review(evidence_key, reason,            -- 'conflict_resolution' | 'source_error'
                 resolved_direction, rationale,
                 citation,                        -- required for source_error
                 reviewed_by, reviewed_at)        -- named human, enforced
itp_experiment_override(evidence_key, experiment_id, reviewed_by, reviewed_at, note)

harm_review(                     -- the ONLY route into v_harm_signal (§5.7)
  compound_id INTEGER PRIMARY KEY,
  decision TEXT NOT NULL,        -- 'surface' | 'reject'
  human_exposure_basis TEXT,     -- required to surface
  rationale TEXT NOT NULL,
  reviewed_by TEXT NOT NULL,     -- a named human; 'auto'/'system'/'pipeline' rejected
  reviewed_at TEXT NOT NULL,
  evidence_keys TEXT NOT NULL    -- JSON array: evidence_key of the rows reviewed
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
carries `entry_route` and `evidence_tier`** (for views showing two compounds, a
prefixed pair such as `basis_evidence_tier`; a test checks every view), output is
produced per route, and **no view combines counts across paths**.

Built:
- `v_animal_evidence` — evidence rows with effective direction (reviews applied), tier, duplicate flag
- `v_evidence_counted` — the same, exact duplicates removed: every count reads this
- `v_direction_review_needed` — unresolved direction conflicts, mammal first
- `v_itp_cohort` — ITP results grouped into cohorts (sex × experiment)
- `v_itp_summary` — ITP arms, cohorts and experiments; ratios overall and by sex; tiers; threshold
- `v_extension_evidence` — extension-path evidence: extension rows only, lab groups, ITP ratio, replication
- `v_itp_null` — ITP-tested compounds below the ITP threshold (null-cell evidence)
- `v_harm_candidates` — harm-path review queue (detection only; surfaces nothing)
- `v_harm_review_context` — each harm candidate's ATC class-mates and their evidence (context only)
- `v_harm_signal` — harm-path deliverable; reads only reviewed `surface` decisions
- `v_mechanistic_human_dossier` — mechanistic path: cocktail premise + human trial counts, labelled
- `v_compound_trials`, `v_extension_replicated`, `v_gold_cell`, `v_untested_candidates`,
  `v_under_tested`, `v_null_cell`, `v_unreported` — the output cells (§1, §11.2)
- `v_orphaned_reviews`, `v_cell_membership_live`, `v_membership_changes`,
  `v_cell_transitions` — change detection (§11)
- `v_class_entry_basis` — which direct compound and ATC class justify each class entry
- `v_atc_review_needed` — multi-class compounds awaiting an ATC decision (§5.5)
- `v_entry_route_check` — stored `entry_route` disagreeing with the data (should be empty)

Still to build:
- `v_compound_summary`
- `v_replication_overlap` — replication resting on shared authorship (§5.4)

The output cells exist but stay empty until trials are normalised (§7 step 5).

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
significance flags (`agesdk/evidence.py`, rule `direction-v2`), never from effect
size alone. First **per measure** (average and maximum lifespan separately):

- significant, with a value → `extension` / `shortening` by sign (a significant 0 is `null`)
- not significant → `null` (*measured, no effect detected*)
- anything else → `unassessed` (*significance not reported, or a flag with no value*).
  **Not** negative evidence: it never feeds the null cell.

Then **combined, symmetrically — no precedence of one measure over the other**:

- **`conflict`** when one measure is significant in one direction and the other measure,
  also assessed (S or NS), has a point estimate in the opposite direction. Levodopa
  (mean +7% NS, max −14% S) is the defining case: that is a disagreement, not a tie to
  break, and maximum lifespan is the more fragile statistic, often resting on the last
  few survivors. Conflicts go to human review (`v_direction_review_needed`,
  `direction_review`) and **count toward no path until resolved**.
- otherwise the significant direction if any measure is significant; else `null` if any
  measure was assessed; else `unassessed`.

Same direction with different significance (17-α-estradiol 2014 males: mean +12% S, max
+5% NS) is agreement measured with different power, not a conflict. A measure without
reported significance cannot create a conflict (sodium cyclamate: mean +9.8% S, max
−11.3% with no significance reported).

In DrugAge Build 5: 1,670 extension, 398 shortening, 1,130 null, 221 unassessed and
**4 conflict** rows (all mammal: levodopa, epitalon, β-aminopropionitrile ×2). All rows
are kept, whatever their direction.

**Reviews attach to evidence, not row numbers.** Each row carries an `evidence_key`, a
content hash of the source row, so a direction or harm review survives a reload of the
normalised layer. `direction_review` also records **source-error corrections**
(`reason = 'source_error'`, citation quoting the primary source required) where the
source misreports the paper; the raw and normalised layers are never edited. Reviews live
in `data/reviews/direction_reviews.yaml` (version controlled; the table is rebuilt from
it). Each names its row by `evidence_key` and by a readable locator; if the source later
changes that row, the check fails and the review surfaces as orphaned rather than
silently re-attaching.

*Corrected so far* (from a check of all 164 DrugAge ITP rows against the papers,
`docs/drugage_itp_audit.md`): female meclizine (DrugAge +3% S; paper log-rank p = 0.40)
and female Protandim (DrugAge +3% S; paper p = 0.291). Each is a verifiable discrepancy
against the primary source. No pattern is claimed: two errors in 98 table-checked rows,
with an error in the other direction alongside (female low-dose acarbose: DrugAge NS,
paper log-rank p = 0.03), is not a finding; the audit document sets out the study that
would test it. Flagged but deliberately **unresolved**: female mycophenolic acid (−1% at
p = 0.05 exactly; its only harm-path evidence) — the case the mandatory harm review
exists for.

**Exact duplicate source rows** (every field identical; 7 in DrugAge Build 5, all
*C. elegans*) are kept but counted once (`v_evidence_counted`).

**Extension-path entry** requires ≥1 result with significant lifespan **extension**.
"Measured lifespan effect" was underspecified and admitted diethylnitrosamine, a
carcinogen; shortening and null results never qualify a compound for this path
and never carry class entry.

**Replicated** extension means either:
- ≥ `replication_min_lab_groups` (2) independent lab groups with significant extension, OR
- an ITP tier of **strong**.

A weak or mixed ITP tier is a single result, not replication. The ITP *threshold* (≥1
positive cohort) is used only to separate ITP nulls (the null cell) from everything else.

**ITP evidence is a ratio, not a boolean — and the unit matters.** Three units:

- **arm** — one ITP result row in the source (one sex × one dose / start age / regimen);
- **experiment** — one independent ITP study: the PMID by default, overridable in
  `itp_experiment_override` where one paper holds several experiments or one experiment
  is reported across papers;
- **cohort** — one sex within one experiment. **This is the unit of the ratio.** Arms
  in the same experiment share a control group and are not independent. A cohort is
  positive if any of its arms shows significant extension.

The map reports arms, cohorts and experiments, cohorts overall and by sex, and a tier.

*Duplication check (2026-11-11).* DrugAge's 164 ITP rows come from 15 papers. No ITP
cohort is entered twice across papers; the one probable cross-paper re-report (the
three-dose NDGA experiment, described in both PMID 24245565 and PMID 27312235) appears
once, under 27312235. Canagliflozin's two papers are independent (the 2024 study used
mice born in 2020 and repeated the 6-month arm). The distortion was arms vs cohorts:
aspirin's 1/6 arms is 1/4 cohorts across 2 experiments.

**Threshold and tiers** (all held as data in `analysis_threshold`; the views apply
them, nobody adjudicates compounds):

- *meets threshold*: ≥ `itp_min_positive_cohorts` (1) positive cohort, positive
  fraction ≥ `itp_min_positive_fraction` (0.0).
- *tier*, overall and per sex:
  - **strong** — ≥2 positive cohorts, ≥0.5 of cohorts positive, **and positive cohorts in
    ≥2 independent experiments** (two sexes of one experiment share cohort, housing and
    conditions: not replication)
  - **weak** — a single positive cohort and fewer than half positive
  - **mixed** — any other result with ≥1 positive (including a lone 1/1)
  - **none** — tested, no positive cohort

| Compound | Experiments | Arms | Cohorts | Male | Female | Tier (overall / M / F) |
|---|---|---|---|---|---|---|
| rapamycin | 4 | 14/16 | 8/8 | 4/4 | 4/4 | strong / strong / strong |
| acarbose | 3 | 9/10 | 6/6 | 3/3 | 3/3 | strong / strong / strong |
| 17-α-estradiol | 3 | 4/6 | 3/5 | 3/3 | 0/2 | strong / strong / none |
| canagliflozin | 2 | 3/6 | 2/4 | 2/2 | 0/2 | strong / strong / none |
| aspirin | 2 | 1/6 | 1/4 | 1/2 | 0/2 | **weak** / mixed / none |
| captopril | 1 | 2/2 | 2/2 | 1/1 | 1/1 | **mixed** / mixed / mixed |
| meclizine (corrected) | 1 | 1/2 | 1/2 | 1/1 | 0/1 | **mixed** / mixed / none |
| resveratrol | 2 | 0/6 | 0/4 | 0/2 | 0/2 | none |

Strong in DrugAge Build 5 (with corrections): rapamycin, acarbose, 17-α-estradiol,
canagliflozin, NDGA. Single-experiment results (captopril, glycine, meclizine,
Protandim, astaxanthin and others) read mixed; aspirin reads weak.

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
- `v_harm_candidates` is the review queue. Appearing in it surfaces nothing. Unresolved
  mammalian direction conflicts are counted beside each candidate but never qualify one.
- **Class context.** Class-related harm is a real and historically important pattern
  (the COX-2 withdrawals were a class story). `v_harm_review_context` shows the reviewer
  each candidate's ATC class-mates (specific classes only, never residual) with their own
  mammal shortening, extension and conflict counts and their harm-review state. The
  reviewer sees the class; **entry still requires the compound's own direct evidence**.
- If evidence changes after review (rows added or withdrawn), `v_harm_signal` flags
  `evidence_changed_since_review` and `still_meets_threshold`; the decision is
  revisited, not silently kept.

A false positive here does real damage. The harm signal is a pointer to published
animal evidence that deserves attention, never a claim that a drug is unsafe in
humans.

**Never merged.** A compound on both paths is reported in both, with each path's
counts computed from its own direction only.

### 5.8 Mechanistic path: chemical reprogramming

**Inclusion rule, deliberately tight:** the compound appeared as a **named component of a
published chemical reprogramming cocktail**. Not "regenerative medicine" broadly; not
single agents; not compounds used only as inhibitor controls.

**Standard: the same as DrugAge's — no bare names.** Every row in
`reprogramming_evidence` must carry, and the schema rejects a row without:

- a PMID or DOI (format-checked);
- the cocktail's name and its components as the paper wrote them (≥2 components);
- the cell type and species, and whether in vivo;
- the kind of demonstration (`full_pluripotency` | `partial_reprogramming_rejuvenation` |
  `transdifferentiation`) and **what was actually demonstrated**, in words;
- whether that was verified from full text or abstract; who recorded it and when.

Curated in `data/reference/reprogramming_evidence.yaml`, version controlled. Component
identity follows §5.1 (full InChIKey); unresolved identities are recorded but not loaded.

**Grading.** Components with no lifespan evidence are `mechanistic_only`, entry route
`reprogramming_cocktail`. A component already in DrugAge (valproic acid, sodium
butyrate, alpha-ketoglutarate) stays `measured_lifespan`; its cocktail rows are context.

**Output.** These compounds **never enter the gold cell**, which requires measured
lifespan evidence. Their deliverable is `v_mechanistic_human_dossier`: cocktails,
citations, cell types, whether anything was shown in vivo, review state, and systemic
human trial counts — every row stating the premise: *"Mechanistic premise only: named
component of a published chemical reprogramming cocktail. No measured lifespan evidence."*

**Seeded from** Yang et al. 2023, *Aging* (PMID 37437248, DOI 10.18632/aging.204896),
read in full text. Six cocktails, all in replicatively senescent human fibroblasts in
vitro over 4 days; they restored nucleocytoplasmic compartmentalization and reduced
transcriptomic age without pluripotency markers. No lifespan was measured.

| Cocktail | Components (as written) | Composition |
|---|---|---|
| C1 (VC6TF) | valproic acid, CHIR-99021, E-616452 (RepSox), tranylcypromine, forskolin | complete |
| C2 | C1 + sodium butyrate | additives in Suppl. Table 2, not read |
| C3 | C1 + bFGF | additives in Suppl. Table 2, not read |
| C4 (C6NYSA) | CHIR-99021, E-616452, TTNPB, Y-27632, Smoothened Agonist, ABT-869 (linifanib) | complete |
| C5 | C4 + sodium butyrate | additives in Suppl. Table 2, not read |
| C6 | C4 + alpha-ketoglutarate | additives in Suppl. Table 2, not read |

Loaded as `mechanistic_only`: CHIR-99021, RepSox, tranylcypromine, forskolin, TTNPB,
Y-27632, linifanib. Not loaded pending decisions: "Smoothened Agonist" (the paper does
not say which; SAG is likely) and bFGF (a protein, not a small molecule).

Identity trap found: PubChem titles Y-27632's record (CID 448042) "Ximelegatran", one
letter from ximelagatran, an unrelated withdrawn anticoagulant.

**Not yet meeting the standard** (recorded under `pending`, never loaded): the founding
chemical-iPSC papers, Hou et al. 2013 *Science* (PMID 23868920) and Guan et al. 2022
*Nature* (PMID 35418683), whose cocktails are not named in their abstracts and whose full
text is not open access; and a 2022 bioRxiv preprint reporting a chemical cocktail that
extends *C. elegans* lifespan — if published, that is lifespan evidence for the measured
path, not this one.

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
- How often do DrugAge significance flags disagree with primary sources? The ITP pilot
  (`docs/drugage_itp_audit.md`) found two clear errors and one in the opposite direction
  in 98 rows — too few to characterise; a stratified, double-extracted study of
  mammalian rows is outlined there.
- Mechanistic path: is a growth factor (bFGF) a "compound" here? Which "Smoothened
  Agonist" did Yang 2023 use (Supplementary Table 1)?
- Full text of Hou 2013 and Guan 2022 is needed before their cocktails can be recorded.

---

## 11. Refresh and change detection

**A diff, not a monitor.** Each run refreshes the sources, re-processes what changed,
snapshots derived-view membership, compares it with the previous completed run, and
emits a reviewable changelog. No notification streams. Implemented in
`agesdk/refresh.py`; run with `python -m agesdk refresh`.

### 11.1 Source refresh

- **DrugAge.** Download and compare the archive's SHA-256 with the hash stored in the
  raw layer. Unchanged: nothing is re-processed. Changed: the new members are appended
  to `raw_response`, and DrugAge `animal_evidence` is rebuilt from the new build for
  every mapped compound (`compound_synonym`, source `drugage`).
- **ClinicalTrials.gov.** Per intervention term, only studies whose
  `LastUpdatePostDate` is on or after the term's high-water mark (minus a 1-day
  overlap) are requested. The mark is the registry's own data date (`/version`
  `dataTimestamp`) at the last successful fetch. A term never fetched before gets its
  full history. A failed fetch is logged and does not advance the mark.
- **Every refresh appends fetch metadata** to `fetch_log` (raw layer, append-only, same
  no-update/no-delete triggers as `raw_response`): source, request, time, outcome
  (`changed` | `unchanged` | `error`), the raw row it resolved to, content hash and
  high-water mark. Unchanged content is not stored again in `raw_response`; the log is
  the history of every check.

### 11.2 Change classes

| # | Change | Treatment |
|---|---|---|
| 1 | New compound appears in a DrugAge build | churn — logged |
| 2 | Existing compound gains a trial | churn — logged |
| 3 | Trial changes state (results posted, crosses into `NOT_POSTED_DUE`) | churn — logged |
| 4 | A compound crosses into a derived cell it wasn't in before | **surfaced** |

Class 3 is per trial; the corresponding class-4 event is per compound: *the compound*
enters the unreported cell when one of its systemic trials becomes overdue.

`v_cell_transitions` lists the surfaced transitions between consecutive completed runs:

| Transition | Meaning |
|---|---|
| `entered_gold_cell` | replicated mammalian extension and now has systemic human trials |
| `left_under_tested` | gained a systemic trial with an ageing-adjacent endpoint |
| `new_harm_candidate` | new credible mammalian shortening (still needs human review) |
| `results_now_overdue` | a systemic trial of the compound crossed into `NOT_POSTED_DUE` |
| `itp_tier_changed` | ITP tier changed (or first ITP result) |
| `harm_review_needs_revisit` | a surfaced harm decision's evidence changed (the guard, §11.6) |
| `review_orphaned` | a reviewed decision's evidence no longer exists (the guard, §11.6) |

The last two are additions to the five requested: they are how the guard becomes visible.
`v_membership_changes` holds every change (entered / left / state changed, churn
included) for audit. The first run is a baseline and reports nothing.

The derived cells behind these (`v_gold_cell`, `v_untested_candidates`,
`v_under_tested`, `v_null_cell`, `v_unreported`) use *mammal* replication: ≥2 mammal lab
groups or a **strong** ITP tier. Class-entered compounds inherit their basis compound's
replication and carry `inherited_class` throughout.

### 11.3 Snapshots

`snapshot_run` records each run (time, status, schema and code version, and the source
versions it saw: DrugAge build and archive hash, ClinicalTrials.gov API version and data
date, literature query version and window). `snapshot_membership` stores every derived
cell's membership per run, with the compound's tier and route and the evidence at that
moment (ITP cohorts and tier, trial counts, evidence keys). Transitions are computed
from this stored state, not recomputed, so the map can show **when a compound entered a
cell and on what evidence**. Both tables are append-only; a finished run cannot be
altered; failed runs are excluded from comparison. They are never rebuilt by schema
upgrades.

### 11.4 Literature scan for pre-database signals

Europe PMC search on lifespan-extension terms, run with each refresh over the window
since the previous scan (7 days on a first run), query versioned in
`data/rules/literature_scan.yaml` (`litscan-v1`). For each hit, Europe PMC's text-mined
chemical annotations are compared against compound names and synonyms already in the map
and against DrugAge; papers naming only known compounds, or only reagents on the
versioned stoplist, are dropped. The rest land in `literature_candidate` as `queued`.

**A curation queue only — never automatic entry, under any circumstances.** There is no
foreign key or code path from `literature_candidate` into `compound`; the scanner writes
only to the queue and the fetch log (a test traces its SQL to prove it); a candidate
leaves `queued` only with a named human reviewer. Anything curated enters by the normal
routes. The harm path's mandatory-review rule applies in full.

Expect noise. Test week 2026-11-04..11: 6 hits, of which obtusifolin (*C. elegans*) was
the one plausible signal. Tune the query and stoplist over time; bump the version on
every change so each candidate records the query that found it.

### 11.5 Scheduling

`.github/workflows/weekly-refresh.yml`: GitHub Action. It lives with the code and leaves a
commit trail. **It is currently manual-only (`workflow_dispatch`); there is no schedule.**

*Why not weekly, yet.* The job cannot detect transitions until the normalised layer
exists: with no compound mappings or normalised trials, `v_cell_transitions` cannot fire,
so a weekly run would produce near-empty output. A recurring job that mostly reports
nothing is one you stop reading, which is how you miss the run that matters. Nor does the
tempo of the data justify weekly: DrugAge releases roughly annually, and trial state
changes are slow.

*When to turn it back on.* After trial normalisation (§7 step 5) is complete and
`v_cell_transitions` can actually fire. **Reassess the cadence then** rather than
defaulting to weekly. Re-enabling is one line (uncomment the `schedule:` line in the
workflow); the Action, state backups and literature scan are kept intact and tested
(`tests/test_workflow.py`, `tests/test_refresh.py`, `tests/test_state_backups.py`).

Each run, whether manual or scheduled:

1. Restore the database from the newest `pipeline-state-YYYY-MM-DD-run<N>` release
   (none on first run: that run is the baseline).
2. Run the tests, then `refresh`.
3. **If `v_cell_transitions` is non-empty for the run:** commit
   `changelog/<date>-run<id>.md` and open an issue with the same text. **Otherwise do
   nothing** — no commit, no issue.
4. Save the database as a **new dated release** — never overwrite. Only after the new
   asset is confirmed present, prune older backups: keep the newest 12, and beyond those
   the newest backup of each calendar month, indefinitely (`agesdk/state_backups.py`).
   Counts are of backups, not weeks, so the policy holds at any cadence.
   Publishing happens before saving, so a failed save repeats a changelog next week
   rather than losing one.

State lives in releases because the database (raw layer, snapshot history, reviews) is
too large and binary for git. The snapshot design's value is its history, so no single
mutable artefact holds it: one bad upload costs at most one run. Release assets of a
public repository are public; the database holds only public-source data, reviews and
the literature queue.

### 11.6 Guard: a refresh never silently changes a reviewed decision

- Refresh writes only to the raw layer, `fetch_log`, the rebuildable normalised layer,
  snapshots and the literature queue — never to `harm_review`, `direction_review`,
  `itp_experiment_override`, `compound_relation`, ATC reviews or the crosswalk.
- **Harm path.** If new evidence arrives for a compound with a harm review, the existing
  `evidence_changed_since_review` flag fires and surfaces as
  `harm_review_needs_revisit`. The review does not update, and the compound neither
  enters nor leaves `v_harm_signal` without a human (tested across runs, including when
  the evidence is withdrawn).
- **Orphaned reviews.** Reviews attach to `evidence_key`, a hash of the source row. If a
  new DrugAge build corrects a row, its key changes and the review would silently stop
  applying; instead it appears in `v_orphaned_reviews` and surfaces as `review_orphaned`.
