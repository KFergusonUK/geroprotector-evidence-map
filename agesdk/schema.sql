-- Geroprotector Human Evidence Map — SQLite schema.
-- Authoritative over the table sketches in SPEC.md §4 if the two ever differ.
-- Idempotent: safe to run against an existing database. Tables and triggers use
-- IF NOT EXISTS; views are dropped and recreated so view edits take effect.

PRAGMA foreign_keys = ON;

-- ===========================================================================
-- 4.1 Raw layer — append-only, verbatim
-- ===========================================================================

CREATE TABLE IF NOT EXISTS raw_response (
  id              INTEGER PRIMARY KEY,
  source          TEXT NOT NULL,          -- 'drugage' | 'ctgov' | 'pubchem' | 'chembl' | 'europepmc' | 'openalex'
  endpoint        TEXT NOT NULL,          -- URL path, or 'archive.zip!member' for archive members
  request_params  TEXT NOT NULL,          -- canonical JSON (sorted keys, no whitespace)
  response_body   TEXT NOT NULL,          -- JSON / CSV / HTML exactly as returned (UTF-8)
  http_status     INTEGER,
  fetched_at      TEXT NOT NULL,          -- ISO 8601 UTC
  api_version     TEXT,
  content_sha256  TEXT NOT NULL,          -- sha256 of response_body; idempotency key
  response_meta   TEXT                    -- JSON: selected headers, archive hashes, member name, ...
);

CREATE INDEX IF NOT EXISTS ix_raw_key
  ON raw_response (source, endpoint, request_params, fetched_at);

-- "Never overwrite; append a new row and supersede."
CREATE TRIGGER IF NOT EXISTS raw_response_no_update
BEFORE UPDATE ON raw_response
BEGIN SELECT RAISE(ABORT, 'raw_response is append-only'); END;

CREATE TRIGGER IF NOT EXISTS raw_response_no_delete
BEFORE DELETE ON raw_response
BEGIN SELECT RAISE(ABORT, 'raw_response is append-only'); END;

-- ===========================================================================
-- 4.2 Normalised layer
-- ===========================================================================

CREATE TABLE IF NOT EXISTS compound (
  compound_id     INTEGER PRIMARY KEY,
  canonical_name  TEXT NOT NULL UNIQUE,
  pubchem_cid     INTEGER UNIQUE,         -- nullable: some will not resolve
  -- Full 27-character InChIKey only. The first 14-char block encodes
  -- connectivity without stereochemistry, so 17α- and 17β-estradiol share it.
  inchikey        TEXT UNIQUE CHECK (
                    inchikey IS NULL OR (
                      length(inchikey) = 27 AND
                      inchikey GLOB '[A-Z][A-Z][A-Z][A-Z][A-Z][A-Z][A-Z][A-Z][A-Z][A-Z][A-Z][A-Z][A-Z][A-Z]-[A-Z][A-Z][A-Z][A-Z][A-Z][A-Z][A-Z][A-Z][A-Z][A-Z]-[A-Z]')),
  chembl_id       TEXT UNIQUE,
  is_mixture      INTEGER NOT NULL DEFAULT 0 CHECK (is_mixture IN (0, 1)),
  -- Mechanism of entry (SPEC §1):
  --   'direct'                 has measured animal lifespan evidence itself (DrugAge)
  --   'class'                  shares an ATC level-4 class with a 'direct' compound (one hop)
  --   'reprogramming_cocktail' named component of a published chemical reprogramming
  --                            cocktail (reprogramming_evidence), no lifespan evidence
  entry_route     TEXT NOT NULL CHECK (entry_route IN ('direct', 'class', 'reprogramming_cocktail')),
  -- Evidential grade (SPEC §1). Every compound-level view carries it; no view shows a
  -- compound in a count without it. Where a compound qualifies several ways, the
  -- strongest grade wins: measured_lifespan > inherited_class > mechanistic_only.
  evidence_tier   TEXT NOT NULL CHECK (evidence_tier IN ('measured_lifespan', 'inherited_class', 'mechanistic_only')),
  notes           TEXT,
  CHECK ((entry_route = 'direct'                 AND evidence_tier = 'measured_lifespan') OR
         (entry_route = 'class'                  AND evidence_tier = 'inherited_class') OR
         (entry_route = 'reprogramming_cocktail' AND evidence_tier = 'mechanistic_only'))
);

-- Mixtures link to their parents (SPEC §5.1).
CREATE TABLE IF NOT EXISTS compound_component (
  mixture_id      INTEGER NOT NULL REFERENCES compound (compound_id),
  component_id    INTEGER NOT NULL REFERENCES compound (compound_id),
  PRIMARY KEY (mixture_id, component_id),
  CHECK (mixture_id <> component_id)
);

CREATE TABLE IF NOT EXISTS compound_synonym (
  compound_id     INTEGER NOT NULL REFERENCES compound (compound_id),
  synonym         TEXT NOT NULL,
  source          TEXT NOT NULL,          -- where this string was observed
  PRIMARY KEY (compound_id, synonym)
);

-- ATC classes, sourced from ChEMBL. Many-to-many: aspirin is in B01AC and N02BA.
CREATE TABLE IF NOT EXISTS compound_atc (
  compound_id     INTEGER NOT NULL REFERENCES compound (compound_id),
  atc_code        TEXT NOT NULL CHECK (
                    length(atc_code) = 7 AND
                    atc_code GLOB '[A-Z][0-9][0-9][A-Z][A-Z][0-9][0-9]'),
  atc_level4      TEXT GENERATED ALWAYS AS (substr(atc_code, 1, 5)) STORED,
  source          TEXT NOT NULL DEFAULT 'chembl',
  source_chembl_id TEXT,
  raw_response_id INTEGER REFERENCES raw_response (id),
  -- Only 'auto' and 'accepted' rows can carry class entry.
  --   auto           — compound has exactly one specific level-4 class
  --   pending_review — compound has >1 specific level-4 class; blocks class entry until reviewed
  --   accepted / rejected — a human decision on whether this class may carry class entry
  --   residual       — an 'other/various' bucket (level 4 ending in X). Residual groupings are
  --                    not mechanisms: they NEVER carry class entry, reviewed or not.
  review_status   TEXT NOT NULL DEFAULT 'pending_review'
                    CHECK (review_status IN ('auto', 'pending_review', 'accepted', 'rejected', 'residual')),
  reviewed_by     TEXT,
  reviewed_at     TEXT,
  note            TEXT,
  PRIMARY KEY (compound_id, atc_code),
  CHECK (review_status NOT IN ('accepted', 'rejected') OR reviewed_by IS NOT NULL),
  CHECK ((substr(atc_code, 5, 1) = 'X') = (review_status = 'residual'))
);

CREATE INDEX IF NOT EXISTS ix_compound_atc_l4 ON compound_atc (atc_level4);

-- Chemical reprogramming evidence (SPEC §5.8): the premise for the third entry path.
-- To the standard DrugAge meets: no bare names. Every row must say where (PMID or
-- DOI), which cocktail, its components, which cells, and what was demonstrated.
-- Curated in data/reference/reprogramming_evidence.yaml and loaded from there.
CREATE TABLE IF NOT EXISTS reprogramming_evidence (
  id                     INTEGER PRIMARY KEY,
  compound_id            INTEGER NOT NULL REFERENCES compound (compound_id),
  source_component_name  TEXT NOT NULL CHECK (length(trim(source_component_name)) > 0),  -- as the paper wrote it
  citation_pmid          TEXT CHECK (citation_pmid IS NULL OR (citation_pmid GLOB '[1-9]*' AND citation_pmid NOT GLOB '*[^0-9]*')),
  citation_doi           TEXT CHECK (citation_doi IS NULL OR citation_doi LIKE '10.%/%'),
  cocktail_name          TEXT NOT NULL CHECK (length(trim(cocktail_name)) > 0),
  cocktail_components    TEXT NOT NULL CHECK (json_valid(cocktail_components)
                           AND json_type(cocktail_components) = 'array'
                           AND json_array_length(cocktail_components) >= 2),  -- a cocktail, not a single agent
  composition_complete   INTEGER NOT NULL CHECK (composition_complete IN (0, 1)),
  cell_type              TEXT NOT NULL CHECK (length(trim(cell_type)) > 0),
  cell_species           TEXT NOT NULL CHECK (length(trim(cell_species)) > 0),
  in_vivo                INTEGER NOT NULL CHECK (in_vivo IN (0, 1)),
  demonstration_kind     TEXT NOT NULL CHECK (demonstration_kind IN (
                           'full_pluripotency', 'partial_reprogramming_rejuvenation', 'transdifferentiation')),
  demonstrated           TEXT NOT NULL CHECK (length(trim(demonstrated)) >= 40),  -- what was actually shown
  verified_from          TEXT NOT NULL CHECK (verified_from IN ('full_text', 'abstract')),
  recorded_by            TEXT NOT NULL CHECK (length(trim(recorded_by)) > 0),
  recorded_at            TEXT NOT NULL,
  reviewed_by            TEXT,
  reviewed_at            TEXT,
  note                   TEXT,
  CHECK (citation_pmid IS NOT NULL OR citation_doi IS NOT NULL),
  CHECK (reviewed_by IS NULL OR reviewed_at IS NOT NULL),
  UNIQUE (compound_id, cocktail_name, citation_pmid, citation_doi)
);

-- Reviewed links between compound rows that stay separate (SPEC §5.1).
-- same_substance_as: e.g. NDGA (stereo undefined) and masoprocol (meso-NDGA).
-- Never used to override a canonical InChIKey or to merge counts. Symmetric,
-- so stored once with the lower id first.
CREATE TABLE IF NOT EXISTS compound_relation (
  compound_id         INTEGER NOT NULL REFERENCES compound (compound_id),
  related_compound_id INTEGER NOT NULL REFERENCES compound (compound_id),
  relation            TEXT NOT NULL CHECK (relation IN ('same_substance_as')),
  reviewed_by         TEXT NOT NULL CHECK (length(trim(reviewed_by)) > 0),
  reviewed_at         TEXT NOT NULL,
  note                TEXT,
  PRIMARY KEY (compound_id, related_compound_id, relation),
  CHECK (compound_id < related_compound_id)
);

-- Documented thresholds the derived views apply (SPEC §5.4, §5.7). Views read
-- these; nobody adjudicates individual compounds.
CREATE TABLE IF NOT EXISTS analysis_threshold (
  name      TEXT PRIMARY KEY,
  value     REAL NOT NULL,
  rationale TEXT NOT NULL
);

INSERT OR IGNORE INTO analysis_threshold (name, value, rationale) VALUES
  ('itp_min_positive_cohorts', 1,
   'SPEC §5.4: ≥1 ITP cohort (one sex in one independent experiment) with significant extension. Ratio and tier always shown alongside.'),
  ('itp_min_positive_fraction', 0.0,
   'Minimum positive/total ITP cohorts. 0 = no requirement beyond the cohort count; the tier carries the strength.'),
  ('itp_tier_strong_min_positive', 2,
   'Tier strong: at least this many positive cohorts, and ...'),
  ('itp_tier_strong_min_fraction', 0.5,
   '... at least this fraction of cohorts positive, and ...'),
  ('itp_tier_strong_min_experiments', 2,
   '... positive cohorts in at least this many independent experiments. The two sexes of one experiment share cohort, housing and conditions: not independent replication.'),
  ('itp_tier_weak_max_positive', 1,
   'Tier weak: at most this many positive cohorts, and ...'),
  ('itp_tier_weak_below_fraction', 0.5,
   '... positive fraction below this (the majority of cohorts not positive). Anything else with ≥1 positive is mixed.'),
  ('replication_min_lab_groups', 2,
   'SPEC §5.4: ≥2 independent lab groups (senior author + affiliation) with significant extension.'),
  ('harm_min_mammal_shortening_rows', 1,
   'SPEC §5.7: a single credible mammalian signal surfaces a harm candidate (sensitive by design).');

-- Tiering is a view over this table, never a deletion (SPEC §1.1).
CREATE TABLE IF NOT EXISTS species_taxon (
  species         TEXT PRIMARY KEY,       -- as written in the source
  tier            TEXT NOT NULL CHECK (tier IN ('mammal', 'other_vertebrate', 'invertebrate', 'fungus', 'other')),
  ncbi_taxid      INTEGER,
  note            TEXT
);

CREATE TABLE IF NOT EXISTS animal_evidence (
  id                        INTEGER PRIMARY KEY,
  compound_id               INTEGER NOT NULL REFERENCES compound (compound_id),
  species                   TEXT NOT NULL,
  strain                    TEXT,
  sex                       TEXT NOT NULL DEFAULT 'unknown'
                              CHECK (sex IN ('M', 'F', 'both', 'hermaphrodite', 'unknown')),
  dosage                    TEXT,
  age_at_initiation         TEXT,
  treatment_duration        TEXT,
  avg_lifespan_change_pct   REAL,
  avg_lifespan_significance TEXT CHECK (avg_lifespan_significance IN ('S', 'NS')),  -- NULL = not reported
  max_lifespan_change_pct   REAL,
  max_lifespan_significance TEXT CHECK (max_lifespan_significance IN ('S', 'NS')),
  weight_change_pct         REAL,
  weight_change_significance TEXT CHECK (weight_change_significance IN ('S', 'NS')),
  -- Direction of effect (SPEC §5.4), derived by agesdk.evidence.derive_direction.
  -- Per measure: 'extension' | 'shortening' (significant), 'null' (measured, not
  -- significant), 'unassessed' (no significance reported: NOT negative evidence).
  avg_direction             TEXT NOT NULL
                              CHECK (avg_direction IN ('extension', 'shortening', 'null', 'unassessed')),
  max_direction             TEXT NOT NULL
                              CHECK (max_direction IN ('extension', 'shortening', 'null', 'unassessed')),
  -- Combined. Average and maximum are treated symmetrically; no precedence. Where
  -- they point in opposite directions the row is 'conflict' and goes to human review
  -- (direction_review); until resolved it counts toward no path.
  direction                 TEXT NOT NULL
                              CHECK (direction IN ('extension', 'shortening', 'null', 'unassessed', 'conflict')),
  direction_conflict        INTEGER NOT NULL CHECK (direction_conflict IN (0, 1)),
  direction_rule_version    TEXT NOT NULL,
  -- Stable content hash of the source row: survives reloads, so reviews keyed on it persist.
  evidence_key              TEXT NOT NULL,
  is_itp                    INTEGER NOT NULL DEFAULT 0 CHECK (is_itp IN (0, 1)),
  pmid                      TEXT,           -- joins publication.pmid; no FK, publications load later
  source                    TEXT NOT NULL DEFAULT 'drugage',
  source_compound_name      TEXT NOT NULL,  -- verbatim source string, unmodified
  raw_response_id           INTEGER REFERENCES raw_response (id),
  source_row_number         INTEGER,        -- 1-based data row within that raw response
  UNIQUE (raw_response_id, source_row_number),
  CHECK ((direction = 'conflict') = (direction_conflict = 1))
);

CREATE INDEX IF NOT EXISTS ix_animal_evidence_compound ON animal_evidence (compound_id);
CREATE INDEX IF NOT EXISTS ix_animal_evidence_key ON animal_evidence (evidence_key);

-- Human override of a row's direction (SPEC §5.4). Keyed on evidence_key so a
-- decision survives a reload of the normalised layer. Two uses:
--   conflict_resolution — the row's measures point in opposite directions
--   source_error        — the source misreports the publication (citation required)
-- The raw and normalised layers are never edited; the override is applied in v_animal_evidence.
CREATE TABLE IF NOT EXISTS direction_review (
  evidence_key        TEXT PRIMARY KEY,
  reason              TEXT NOT NULL CHECK (reason IN ('conflict_resolution', 'source_error')),
  resolved_direction  TEXT NOT NULL
                        CHECK (resolved_direction IN ('extension', 'shortening', 'null', 'unassessed')),
  rationale           TEXT NOT NULL CHECK (length(trim(rationale)) > 0),
  citation            TEXT,               -- e.g. 'PMID:38041783 abstract'
  reviewed_by         TEXT NOT NULL CHECK (
                        length(trim(reviewed_by)) > 0 AND
                        lower(trim(reviewed_by)) NOT IN ('auto', 'automatic', 'system', 'pipeline', 'script', 'default')),
  reviewed_at         TEXT NOT NULL CHECK (length(trim(reviewed_at)) > 0),
  CHECK (reason <> 'source_error' OR length(trim(coalesce(citation, ''))) > 0)
);

-- ITP experiment identity (SPEC §5.4). By default an experiment is one PMID; this
-- table overrides that where one paper reports several independent experiments or
-- one experiment is reported across papers.
CREATE TABLE IF NOT EXISTS itp_experiment_override (
  evidence_key    TEXT PRIMARY KEY,
  experiment_id   TEXT NOT NULL CHECK (length(trim(experiment_id)) > 0),
  reviewed_by     TEXT NOT NULL CHECK (length(trim(reviewed_by)) > 0),
  reviewed_at     TEXT NOT NULL,
  note            TEXT
);

-- Publications behind animal evidence; lab_group derivation (SPEC §5.4).
CREATE TABLE IF NOT EXISTS publication (
  pmid                TEXT PRIMARY KEY,
  title               TEXT,
  journal             TEXT,
  pub_year            INTEGER,
  senior_author       TEXT,               -- last author, from Europe PMC
  senior_author_orcid TEXT,
  senior_affiliation  TEXT,
  lab_group           TEXT,               -- normalised senior author + institution
  lab_group_method    TEXT CHECK (lab_group_method IN ('derived', 'manual')),
  raw_response_id     INTEGER REFERENCES raw_response (id)
);

-- Full author list, so replication resting on overlapping authorship can be flagged.
CREATE TABLE IF NOT EXISTS publication_author (
  pmid            TEXT NOT NULL REFERENCES publication (pmid),
  position        INTEGER NOT NULL,       -- 1-based
  full_name       TEXT NOT NULL,
  orcid           TEXT,
  affiliation     TEXT,
  PRIMARY KEY (pmid, position)
);

-- Harm path (SPEC §5.7): mandatory human review. Nothing reaches v_harm_signal
-- except through a row here, and a row here cannot exist without a named
-- human reviewer, a rationale and, to surface, a stated human-exposure basis.
CREATE TABLE IF NOT EXISTS harm_review (
  compound_id           INTEGER PRIMARY KEY REFERENCES compound (compound_id),
  decision              TEXT NOT NULL CHECK (decision IN ('surface', 'reject')),
  human_exposure_basis  TEXT,             -- why exposure is substantial (approved drug, common supplement, ...)
  rationale             TEXT NOT NULL CHECK (length(trim(rationale)) > 0),
  reviewed_by           TEXT NOT NULL CHECK (
                          length(trim(reviewed_by)) > 0 AND
                          lower(trim(reviewed_by)) NOT IN ('auto', 'automatic', 'system', 'pipeline', 'script', 'default')),
  reviewed_at           TEXT NOT NULL CHECK (length(trim(reviewed_at)) > 0),
  -- evidence_key values of the rows reviewed (stable across reloads)
  evidence_keys         TEXT NOT NULL CHECK (json_valid(evidence_keys) AND json_type(evidence_keys) = 'array'),
  CHECK (decision <> 'surface' OR length(trim(coalesce(human_exposure_basis, ''))) > 0)
);

CREATE TABLE IF NOT EXISTS trial (
  nct_id              TEXT PRIMARY KEY,
  title               TEXT,
  phase               TEXT,
  status              TEXT,
  enrollment          INTEGER,
  start_date          TEXT,
  completion_date     TEXT,
  primary_completion_date TEXT,
  sponsor             TEXT,
  sponsor_class       TEXT,
  results_state       TEXT NOT NULL CHECK (results_state IN (
                        'POSTED', 'PARTIAL', 'PUBLISHED_ONLY', 'NOT_POSTED_DUE',
                        'NOT_POSTED_NOT_DUE', 'TERMINATED_NO_RESULTS', 'WITHDRAWN',
                        'ONGOING', 'UNKNOWN')),
  results_posted_date TEXT,
  raw_response_id     INTEGER REFERENCES raw_response (id)
);

CREATE TABLE IF NOT EXISTS trial_intervention (
  nct_id            TEXT NOT NULL REFERENCES trial (nct_id),
  raw_name          TEXT NOT NULL,        -- as the sponsor wrote it, unmodified
  intervention_type TEXT,
  compound_id       INTEGER REFERENCES compound (compound_id),  -- nullable until matched
  -- Systemic exposure criterion (SPEC §5.6). Identity and route are separate
  -- questions: a sirolimus-eluting stent IS sirolimus, but does not qualify.
  route             TEXT,                 -- as derived from the registry record
  systemic_exposure TEXT CHECK (systemic_exposure IN ('systemic', 'local', 'unclear')),
  route_rule_version TEXT,
  PRIMARY KEY (nct_id, raw_name),
  CHECK (systemic_exposure IS NULL OR route_rule_version IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS trial_condition (
  nct_id          TEXT NOT NULL REFERENCES trial (nct_id),
  condition_text  TEXT NOT NULL,
  mesh_term       TEXT,
  PRIMARY KEY (nct_id, condition_text)
);

CREATE TABLE IF NOT EXISTS trial_outcome (
  id                  INTEGER PRIMARY KEY,
  nct_id              TEXT NOT NULL REFERENCES trial (nct_id),
  outcome_type        TEXT CHECK (outcome_type IN ('primary', 'secondary', 'other')),
  measure             TEXT NOT NULL,
  time_frame          TEXT,
  ageing_adjacent     INTEGER CHECK (ageing_adjacent IN (0, 1)),
  ageing_category     TEXT,
  classifier_version  TEXT                -- rule-set version that produced the classification (§5.3)
);

-- ===========================================================================
-- 4.3 Crosswalk layer — mappings as reviewed data
-- ===========================================================================

CREATE TABLE IF NOT EXISTS crosswalk (
  id              INTEGER PRIMARY KEY,
  from_source     TEXT NOT NULL,
  from_value      TEXT NOT NULL,
  compound_id     INTEGER NOT NULL REFERENCES compound (compound_id),
  method          TEXT NOT NULL CHECK (method IN ('exact', 'synonym', 'fuzzy', 'manual')),
  confidence      REAL NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),
  reviewed_by     TEXT,
  reviewed_at     TEXT,
  note            TEXT,
  UNIQUE (from_source, from_value),
  -- SPEC §5.1: no fuzzy match is accepted without human review.
  CHECK (method <> 'fuzzy' OR reviewed_by IS NOT NULL),
  CHECK (method <> 'manual' OR reviewed_by IS NOT NULL)
);

-- ===========================================================================
-- 4.4 Derived layer — views only. Every compound-level view carries entry_route.
-- ===========================================================================

DROP VIEW IF EXISTS v_raw_current;
CREATE VIEW v_raw_current AS
SELECT r.*
FROM raw_response r
WHERE r.id = (
  SELECT r2.id FROM raw_response r2
  WHERE r2.source = r.source
    AND r2.endpoint = r.endpoint
    AND r2.request_params = r.request_params
  ORDER BY r2.fetched_at DESC, r2.id DESC
  LIMIT 1);

-- ---------------------------------------------------------------------------
-- Effective direction: the source-derived direction, replaced by a human
-- direction_review where one exists (conflict resolution or source-error correction). Every path view reads THIS, never
-- animal_evidence.direction directly. Unresolved conflicts stay 'conflict' and
-- count toward no path.
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS v_animal_evidence;
CREATE VIEW v_animal_evidence AS
SELECT ae.*,
       coalesce(dr.resolved_direction, ae.direction)   AS effective_direction,
       dr.reason                                       AS direction_review_reason,
       dr.reviewed_by                                  AS direction_reviewed_by,
       st.tier                                         AS tier,
       -- Exact duplicate source rows (every field identical; 7 in DrugAge Build 5,
       -- all C. elegans). Kept, but counted once.
       (row_number() OVER (PARTITION BY ae.evidence_key ORDER BY ae.id) > 1) AS is_exact_duplicate,
       cmp.evidence_tier                               AS evidence_tier
FROM animal_evidence ae
JOIN compound cmp             ON cmp.compound_id = ae.compound_id
LEFT JOIN direction_review dr ON dr.evidence_key = ae.evidence_key
LEFT JOIN species_taxon st    ON st.species = ae.species;

-- What every count is computed from: effective direction, exact duplicates removed.
DROP VIEW IF EXISTS v_evidence_counted;
CREATE VIEW v_evidence_counted AS
SELECT * FROM v_animal_evidence WHERE NOT is_exact_duplicate;

-- Conflicts awaiting a human. Mammal rows first: those can affect the harm path.
DROP VIEW IF EXISTS v_direction_review_needed;
CREATE VIEW v_direction_review_needed AS
SELECT v.id, v.evidence_key, v.compound_id, c.canonical_name, v.evidence_tier, v.species, v.tier, v.sex,
       v.avg_lifespan_change_pct, v.avg_lifespan_significance, v.avg_direction,
       v.max_lifespan_change_pct, v.max_lifespan_significance, v.max_direction,
       v.is_itp, v.pmid
FROM v_animal_evidence v
JOIN compound c USING (compound_id)
WHERE v.effective_direction = 'conflict'
ORDER BY (v.tier = 'mammal') DESC, c.canonical_name;

-- ---------------------------------------------------------------------------
-- Class entry (SPEC §5.5)
-- ---------------------------------------------------------------------------

-- Multi-class compounds awaiting a human decision. Residual (…X) rows are
-- excluded by rule and do not count toward 'multi-class'.
DROP VIEW IF EXISTS v_atc_review_needed;
CREATE VIEW v_atc_review_needed AS
WITH per_compound AS (
  SELECT compound_id, count(DISTINCT atc_level4) AS n_level4
  FROM compound_atc WHERE review_status <> 'residual' GROUP BY compound_id)
SELECT c.compound_id, c.canonical_name, c.entry_route, c.evidence_tier,
       ca.atc_code, ca.atc_level4, ca.review_status, pc.n_level4,
       'multi_class' AS reason
FROM compound_atc ca
JOIN compound c ON c.compound_id = ca.compound_id
JOIN per_compound pc ON pc.compound_id = ca.compound_id
WHERE pc.n_level4 > 1
  AND ca.review_status NOT IN ('accepted', 'rejected', 'residual');

-- Why each compound is eligible via class: one hop only, from a 'direct'
-- compound with significant lifespan EXTENSION (shortening never propagates),
-- through a specific class both sides may use (residual buckets never do).
DROP VIEW IF EXISTS v_class_entry_basis;
CREATE VIEW v_class_entry_basis AS
SELECT DISTINCT
  c.compound_id, c.canonical_name, c.entry_route, c.evidence_tier,
  ca.atc_level4,
  b.compound_id    AS basis_compound_id,
  b.canonical_name AS basis_canonical_name,
  b.evidence_tier  AS basis_evidence_tier
FROM compound c
JOIN compound_atc ca ON ca.compound_id = c.compound_id
                    AND ca.review_status IN ('auto', 'accepted')
JOIN compound_atc ba ON ba.atc_level4 = ca.atc_level4
                    AND ba.compound_id <> c.compound_id
                    AND ba.review_status IN ('auto', 'accepted')
JOIN compound b      ON b.compound_id = ba.compound_id
                    AND b.entry_route = 'direct'
WHERE EXISTS (SELECT 1 FROM v_evidence_counted ae
              WHERE ae.compound_id = b.compound_id AND ae.effective_direction = 'extension');

-- Integrity check: stored entry_route vs what the data supports. Should be empty.
DROP VIEW IF EXISTS v_entry_route_check;
CREATE VIEW v_entry_route_check AS
SELECT * FROM (
  SELECT c.compound_id, c.canonical_name, c.entry_route, c.evidence_tier,
         CASE
           WHEN c.entry_route = 'direct'
                AND NOT EXISTS (SELECT 1 FROM animal_evidence ae WHERE ae.compound_id = c.compound_id)
             THEN 'direct_without_animal_evidence'
           WHEN c.entry_route = 'class'
                AND EXISTS (SELECT 1 FROM animal_evidence ae WHERE ae.compound_id = c.compound_id)
             THEN 'class_but_has_animal_evidence'
           WHEN c.entry_route = 'class'
                AND NOT EXISTS (SELECT 1 FROM v_class_entry_basis v WHERE v.compound_id = c.compound_id)
             THEN 'class_without_basis'
           WHEN c.entry_route = 'reprogramming_cocktail'
                AND EXISTS (SELECT 1 FROM animal_evidence ae WHERE ae.compound_id = c.compound_id)
             THEN 'mechanistic_but_has_animal_evidence'
           WHEN c.entry_route = 'reprogramming_cocktail'
                AND EXISTS (SELECT 1 FROM v_class_entry_basis v WHERE v.compound_id = c.compound_id)
             THEN 'mechanistic_but_has_class_basis'
           WHEN c.entry_route = 'reprogramming_cocktail'
                AND NOT EXISTS (SELECT 1 FROM reprogramming_evidence r WHERE r.compound_id = c.compound_id)
             THEN 'mechanistic_without_reprogramming_evidence'
         END AS problem
  FROM compound c)
WHERE problem IS NOT NULL;

-- ---------------------------------------------------------------------------
-- ITP evidence (SPEC §5.4)
--   arm        = one ITP row in the source (one sex x one dose/start age/regimen)
--   experiment = one independent ITP study: PMID by default, or itp_experiment_override
--   cohort     = one sex within one experiment. Arms in the same experiment share a
--                control group, so cohorts, not arms, are the unit of the ratio.
--   A cohort is positive if any of its arms shows significant extension.
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS v_itp_cohort;
CREATE VIEW v_itp_cohort AS
SELECT v.compound_id, v.evidence_tier,
       coalesce(o.experiment_id, 'pmid:' || v.pmid)       AS experiment_id,
       v.sex,
       count(*)                                           AS n_arms,
       sum(v.effective_direction = 'extension')           AS n_arms_positive,
       sum(v.effective_direction = 'shortening')          AS n_arms_shortening,
       sum(v.effective_direction = 'conflict')            AS n_arms_conflict,
       max(v.effective_direction = 'extension')           AS is_positive
FROM v_evidence_counted v
LEFT JOIN itp_experiment_override o ON o.evidence_key = v.evidence_key
WHERE v.is_itp = 1
-- Group on the expression, not the alias: 'experiment_id' would bind to o.experiment_id.
GROUP BY v.compound_id, v.evidence_tier, coalesce(o.experiment_id, 'pmid:' || v.pmid), v.sex;

DROP VIEW IF EXISTS v_itp_summary;
CREATE VIEW v_itp_summary AS
WITH t AS (
  SELECT (SELECT value FROM analysis_threshold WHERE name = 'itp_min_positive_cohorts')     AS min_pos,
         (SELECT value FROM analysis_threshold WHERE name = 'itp_min_positive_fraction')    AS min_frac,
         (SELECT value FROM analysis_threshold WHERE name = 'itp_tier_strong_min_positive') AS s_pos,
         (SELECT value FROM analysis_threshold WHERE name = 'itp_tier_strong_min_fraction') AS s_frac,
         (SELECT value FROM analysis_threshold WHERE name = 'itp_tier_strong_min_experiments') AS s_exp,
         (SELECT value FROM analysis_threshold WHERE name = 'itp_tier_weak_max_positive')   AS w_pos,
         (SELECT value FROM analysis_threshold WHERE name = 'itp_tier_weak_below_fraction') AS w_frac),
agg AS (
  SELECT compound_id,
         count(DISTINCT experiment_id)                AS itp_experiments,
         count(DISTINCT CASE WHEN is_positive THEN experiment_id END) AS itp_experiments_positive,
         sum(n_arms_positive)                         AS itp_arms_positive,
         sum(n_arms)                                  AS itp_arms_total,
         sum(is_positive)                             AS itp_cohorts_positive,
         count(*)                                     AS itp_cohorts_total,
         sum(n_arms_shortening > 0)                   AS itp_cohorts_with_shortening,
         sum(n_arms_conflict > 0)                     AS itp_cohorts_with_conflict,
         sum(CASE WHEN sex = 'M' THEN is_positive END) AS itp_male_positive,
         sum(sex = 'M')                               AS itp_male_total,
         sum(CASE WHEN sex = 'F' THEN is_positive END) AS itp_female_positive,
         sum(sex = 'F')                               AS itp_female_total
  FROM v_itp_cohort GROUP BY compound_id),
tiered AS (
  SELECT agg.*, t.*,
         -- tier(p, n): none | weak | mixed | strong; NULL when nothing tested
         CASE WHEN itp_cohorts_total = 0 THEN NULL
              WHEN itp_cohorts_positive = 0 THEN 'none'
              WHEN itp_cohorts_positive >= s_pos AND 1.0 * itp_cohorts_positive / itp_cohorts_total >= s_frac
                   AND itp_experiments_positive >= s_exp THEN 'strong'
              WHEN itp_cohorts_positive <= w_pos AND 1.0 * itp_cohorts_positive / itp_cohorts_total < w_frac THEN 'weak'
              ELSE 'mixed' END AS itp_tier,
         CASE WHEN itp_male_total = 0 THEN NULL
              WHEN itp_male_positive = 0 THEN 'none'
              WHEN itp_male_positive >= s_pos AND 1.0 * itp_male_positive / itp_male_total >= s_frac
                   AND itp_male_positive >= s_exp THEN 'strong'
              WHEN itp_male_positive <= w_pos AND 1.0 * itp_male_positive / itp_male_total < w_frac THEN 'weak'
              ELSE 'mixed' END AS itp_male_tier,
         CASE WHEN itp_female_total = 0 THEN NULL
              WHEN itp_female_positive = 0 THEN 'none'
              WHEN itp_female_positive >= s_pos AND 1.0 * itp_female_positive / itp_female_total >= s_frac
                   AND itp_female_positive >= s_exp THEN 'strong'
              WHEN itp_female_positive <= w_pos AND 1.0 * itp_female_positive / itp_female_total < w_frac THEN 'weak'
              ELSE 'mixed' END AS itp_female_tier,
         (itp_cohorts_positive >= min_pos
          AND 1.0 * itp_cohorts_positive / itp_cohorts_total >= min_frac) AS meets_itp_threshold
  FROM agg CROSS JOIN t)
SELECT c.compound_id, c.canonical_name, c.entry_route, c.evidence_tier,
       tiered.itp_experiments, tiered.itp_experiments_positive, tiered.itp_arms_positive, tiered.itp_arms_total,
       tiered.itp_cohorts_positive, tiered.itp_cohorts_total,
       tiered.itp_male_positive, tiered.itp_male_total,
       tiered.itp_female_positive, tiered.itp_female_total,
       tiered.itp_cohorts_with_shortening, tiered.itp_cohorts_with_conflict,
       tiered.itp_tier, tiered.itp_male_tier, tiered.itp_female_tier,
       tiered.meets_itp_threshold
FROM tiered JOIN compound c USING (compound_id);

-- ===========================================================================
-- EXTENSION PATH (SPEC §5.4). Conservative. Counts here never include
-- shortening rows, and no view combines this path with the harm path.
-- ===========================================================================

DROP VIEW IF EXISTS v_extension_evidence;
CREATE VIEW v_extension_evidence AS
WITH ext AS (
  SELECT v.compound_id,
         count(*)                                            AS n_extension_rows,
         sum(v.tier = 'mammal')                              AS n_extension_rows_mammal,
         count(DISTINCT v.pmid)                              AS n_extension_pmids,
         count(DISTINCT p.lab_group)                         AS n_extension_lab_groups,
         count(DISTINCT CASE WHEN v.tier = 'mammal' THEN p.lab_group END) AS n_mammal_extension_lab_groups,
         sum(p.lab_group IS NULL)                            AS n_extension_rows_lab_unknown
  FROM v_evidence_counted v
  LEFT JOIN publication p ON p.pmid = v.pmid
  WHERE v.effective_direction = 'extension'
  GROUP BY v.compound_id),
t AS (SELECT value AS min_groups FROM analysis_threshold WHERE name = 'replication_min_lab_groups')
SELECT c.compound_id, c.canonical_name, c.entry_route, c.evidence_tier,
       ext.n_extension_rows, ext.n_extension_rows_mammal, ext.n_extension_pmids,
       ext.n_extension_lab_groups, ext.n_mammal_extension_lab_groups, ext.n_extension_rows_lab_unknown,
       i.itp_experiments,
       coalesce(i.itp_cohorts_positive, 0) AS itp_cohorts_positive,
       coalesce(i.itp_cohorts_total, 0)    AS itp_cohorts_total,
       i.itp_arms_positive, i.itp_arms_total,
       i.itp_male_positive, i.itp_male_total, i.itp_female_positive, i.itp_female_total,
       i.itp_tier, i.itp_male_tier, i.itp_female_tier,
       coalesce(i.meets_itp_threshold, 0)  AS meets_itp_threshold,
       (ext.n_extension_lab_groups >= t.min_groups)             AS replicated_by_lab_groups,
       coalesce(i.itp_tier = 'strong', 0)                       AS replicated_by_itp,
       -- Replication (§5.4): independent lab groups, or a STRONG ITP tier. One positive
       -- cohort (weak) or one experiment's two sexes (mixed) is a single result, not replication.
       (ext.n_extension_lab_groups >= t.min_groups
        OR coalesce(i.itp_tier = 'strong', 0))                  AS replicated,
       (ext.n_mammal_extension_lab_groups >= t.min_groups
        OR coalesce(i.itp_tier = 'strong', 0))                  AS replicated_mammal,
       (ext.n_extension_rows_mammal > 0)                        AS has_mammal_extension
FROM ext
JOIN compound c USING (compound_id)
LEFT JOIN v_itp_summary i USING (compound_id)
CROSS JOIN t;

-- Null cell evidence: ITP-tested and not meeting the ITP threshold. Built from
-- ITP data alone, so it is the exact complement of meets_itp_threshold.
DROP VIEW IF EXISTS v_itp_null;
CREATE VIEW v_itp_null AS
SELECT * FROM v_itp_summary WHERE NOT meets_itp_threshold;

-- ===========================================================================
-- HARM PATH (SPEC §5.7). Sensitive detection, mandatory human review.
-- ===========================================================================

-- Review queue. Detection only: appearing here surfaces nothing. Unresolved
-- mammalian direction conflicts are shown but never qualify a compound.
DROP VIEW IF EXISTS v_harm_candidates;
CREATE VIEW v_harm_candidates AS
WITH sh AS (
  SELECT v.compound_id,
         count(*)                           AS n_mammal_shortening_rows,
         count(DISTINCT v.pmid)             AS n_mammal_shortening_pmids,
         group_concat(DISTINCT v.species)   AS species,
         sum(v.is_itp)                      AS n_itp_shortening_rows,
         json_group_array(v.evidence_key)   AS current_evidence_keys
  FROM v_evidence_counted v
  WHERE v.effective_direction = 'shortening' AND v.tier = 'mammal'
  GROUP BY v.compound_id),
t AS (SELECT value AS min_rows FROM analysis_threshold WHERE name = 'harm_min_mammal_shortening_rows')
SELECT c.compound_id, c.canonical_name, c.entry_route, c.evidence_tier,
       sh.n_mammal_shortening_rows, sh.n_mammal_shortening_pmids, sh.species, sh.n_itp_shortening_rows,
       (SELECT count(*) FROM v_evidence_counted v2
        WHERE v2.compound_id = c.compound_id AND v2.tier = 'mammal'
          AND v2.effective_direction = 'conflict')       AS n_mammal_unresolved_conflicts,
       sh.current_evidence_keys,
       coalesce(hr.decision, 'unreviewed') AS review_state
FROM sh
JOIN compound c USING (compound_id)
CROSS JOIN t
LEFT JOIN harm_review hr USING (compound_id)
WHERE sh.n_mammal_shortening_rows >= t.min_rows;

-- Class context for the harm reviewer. For each harm candidate, its ATC class-mates
-- (specific classes only; residual buckets are not mechanisms) and their evidence.
-- Context only: class-mates do NOT enter the harm path through this view.
DROP VIEW IF EXISTS v_harm_review_context;
CREATE VIEW v_harm_review_context AS
SELECT hc.compound_id                AS candidate_compound_id,
       hc.canonical_name             AS candidate_name,
       hc.evidence_tier              AS candidate_evidence_tier,
       ca.atc_level4,
       m.compound_id                 AS classmate_compound_id,
       m.canonical_name              AS classmate_name,
       m.entry_route                 AS classmate_entry_route,
       m.evidence_tier               AS classmate_evidence_tier,
       (SELECT count(*) FROM v_evidence_counted v WHERE v.compound_id = m.compound_id
          AND v.tier = 'mammal' AND v.effective_direction = 'shortening') AS classmate_mammal_shortening_rows,
       (SELECT count(*) FROM v_evidence_counted v WHERE v.compound_id = m.compound_id
          AND v.tier = 'mammal' AND v.effective_direction = 'extension')  AS classmate_mammal_extension_rows,
       (SELECT count(*) FROM v_evidence_counted v WHERE v.compound_id = m.compound_id
          AND v.tier = 'mammal' AND v.effective_direction = 'conflict')   AS classmate_mammal_conflicts,
       coalesce((SELECT hr.decision FROM harm_review hr WHERE hr.compound_id = m.compound_id),
                CASE WHEN EXISTS (SELECT 1 FROM v_harm_candidates h2 WHERE h2.compound_id = m.compound_id)
                     THEN 'unreviewed' ELSE 'not_a_candidate' END)        AS classmate_harm_state
FROM v_harm_candidates hc
JOIN compound_atc ca ON ca.compound_id = hc.compound_id AND ca.review_status <> 'residual'
JOIN compound_atc ma ON ma.atc_level4 = ca.atc_level4 AND ma.compound_id <> hc.compound_id
                    AND ma.review_status <> 'residual'
JOIN compound m      ON m.compound_id = ma.compound_id
GROUP BY hc.compound_id, ca.atc_level4, m.compound_id;

-- The harm-path deliverable. Reads ONLY from harm_review rows with
-- decision = 'surface'; there is no path into this view without a named reviewer.
DROP VIEW IF EXISTS v_harm_signal;
CREATE VIEW v_harm_signal AS
SELECT c.compound_id, c.canonical_name, c.entry_route, c.evidence_tier,
       hr.human_exposure_basis, hr.rationale, hr.reviewed_by, hr.reviewed_at,
       hc.n_mammal_shortening_rows, hc.n_mammal_shortening_pmids, hc.species,
       (hc.compound_id IS NOT NULL) AS still_meets_threshold,
       -- Evidence added or removed since review: the decision needs revisiting.
       (EXISTS (SELECT 1 FROM json_each(coalesce(hc.current_evidence_keys, '[]')) cur
                WHERE cur.value NOT IN (SELECT value FROM json_each(hr.evidence_keys)))
        OR EXISTS (SELECT 1 FROM json_each(hr.evidence_keys) rev
                   WHERE rev.value NOT IN (SELECT value FROM json_each(coalesce(hc.current_evidence_keys, '[]')))))
         AS evidence_changed_since_review
FROM harm_review hr
JOIN compound c USING (compound_id)
LEFT JOIN v_harm_candidates hc USING (compound_id)
WHERE hr.decision = 'surface';

-- ===========================================================================
-- MECHANISTIC PATH (SPEC §5.8). Chemical reprogramming components with no measured
-- lifespan evidence. Never in the gold cell. This view is their deliverable: what
-- human trial data exists, labelled as resting on a weaker premise.
-- ===========================================================================

DROP VIEW IF EXISTS v_mechanistic_human_dossier;
CREATE VIEW v_mechanistic_human_dossier AS
WITH rp AS (
  SELECT compound_id,
         count(DISTINCT cocktail_name)                                AS n_cocktails,
         group_concat(DISTINCT cocktail_name)                         AS cocktails,
         group_concat(DISTINCT coalesce('PMID:' || citation_pmid, 'DOI:' || citation_doi)) AS citations,
         group_concat(DISTINCT cell_type)                             AS cell_types,
         group_concat(DISTINCT demonstration_kind)                    AS demonstration_kinds,
         max(in_vivo)                                                 AS any_in_vivo,
         min(reviewed_by IS NOT NULL)                                 AS all_rows_reviewed
  FROM reprogramming_evidence GROUP BY compound_id),
tr AS (
  SELECT ti.compound_id,
         count(DISTINCT ti.nct_id)                                    AS n_systemic_trials,
         count(DISTINCT CASE WHEN t.results_state IN ('POSTED', 'PARTIAL', 'PUBLISHED_ONLY')
                             THEN ti.nct_id END)                      AS n_trials_with_results,
         count(DISTINCT CASE WHEN o.ageing_adjacent = 1 THEN ti.nct_id END) AS n_trials_ageing_adjacent
  FROM trial_intervention ti
  JOIN trial t ON t.nct_id = ti.nct_id
  LEFT JOIN trial_outcome o ON o.nct_id = ti.nct_id
  WHERE ti.systemic_exposure = 'systemic' AND ti.compound_id IS NOT NULL
  GROUP BY ti.compound_id)
SELECT c.compound_id, c.canonical_name, c.entry_route, c.evidence_tier,
       'Mechanistic premise only: named component of a published chemical reprogramming '
       || 'cocktail. No measured lifespan evidence for this compound.'  AS premise,
       rp.n_cocktails, rp.cocktails, rp.citations, rp.cell_types, rp.demonstration_kinds,
       rp.any_in_vivo, rp.all_rows_reviewed,
       coalesce(tr.n_systemic_trials, 0)        AS n_systemic_trials,
       coalesce(tr.n_trials_with_results, 0)    AS n_trials_with_results,
       coalesce(tr.n_trials_ageing_adjacent, 0) AS n_trials_ageing_adjacent
FROM compound c
JOIN rp USING (compound_id)
LEFT JOIN tr USING (compound_id)
WHERE c.evidence_tier = 'mechanistic_only';

-- ===========================================================================
-- REGISTRY STAGING (SPEC §7 step 2). ClinicalTrials.gov records as returned, before any
-- resolution. Rebuilt from the raw layer (agesdk.sources.ctgov.stage); the raw layer stays
-- authoritative. Nothing here links a trial to a compound_id: that is the resolver (step 3).
-- ===========================================================================

-- Which strings were searched, and for which fixture compound (query provenance, not identity).
CREATE TABLE IF NOT EXISTS ctgov_query_plan (
  query_term    TEXT PRIMARY KEY,
  compound_key  TEXT NOT NULL,            -- fixture key that supplied the term
  term_source   TEXT NOT NULL CHECK (term_source IN ('canonical_name', 'must_match')),
  plan_version  TEXT NOT NULL
);

-- Every hit, with the query string that produced it: evidence for the precision check (step 4).
CREATE TABLE IF NOT EXISTS ctgov_query_hit (
  query_term            TEXT NOT NULL,
  nct_id                TEXT NOT NULL,
  last_update_post_date TEXT,
  raw_response_id       INTEGER NOT NULL REFERENCES raw_response (id),
  PRIMARY KEY (query_term, nct_id)
);
CREATE INDEX IF NOT EXISTS ix_ctgov_query_hit_nct ON ctgov_query_hit (nct_id);

-- One row per study: the full record as returned (protocolSection, derivedSection,
-- hasResults) plus convenience columns. Later raw responses for a study supersede earlier.
CREATE TABLE IF NOT EXISTS ctgov_study (
  nct_id                   TEXT PRIMARY KEY,
  raw_response_id          INTEGER NOT NULL REFERENCES raw_response (id),
  last_update_post_date    TEXT,
  brief_title              TEXT,
  overall_status           TEXT,
  study_type               TEXT,
  phases                   TEXT CHECK (phases IS NULL OR json_valid(phases)),
  enrollment               INTEGER,
  start_date               TEXT,
  primary_completion_date  TEXT,
  completion_date          TEXT,
  results_first_post_date  TEXT,
  has_results              INTEGER,
  lead_sponsor             TEXT,
  lead_sponsor_class       TEXT,
  interventions            TEXT NOT NULL CHECK (json_valid(interventions)),   -- full array, verbatim
  arm_groups               TEXT CHECK (arm_groups IS NULL OR json_valid(arm_groups)),
  conditions_module        TEXT CHECK (conditions_module IS NULL OR json_valid(conditions_module)),
  condition_browse         TEXT CHECK (condition_browse IS NULL OR json_valid(condition_browse)),      -- MeSH
  intervention_browse      TEXT CHECK (intervention_browse IS NULL OR json_valid(intervention_browse)),-- MeSH
  outcomes_module          TEXT CHECK (outcomes_module IS NULL OR json_valid(outcomes_module)),       -- raw measures
  study_json               TEXT NOT NULL CHECK (json_valid(study_json))      -- the whole record
);

-- One row per intervention object, every field kept (name, type, description, otherNames,
-- armGroupLabels, and anything else the API returns, in object_json).
CREATE TABLE IF NOT EXISTS ctgov_intervention (
  nct_id            TEXT NOT NULL REFERENCES ctgov_study (nct_id),
  idx               INTEGER NOT NULL,      -- position in the study's interventions array
  intervention_type TEXT,
  name              TEXT,
  description       TEXT,
  other_names       TEXT CHECK (other_names IS NULL OR json_valid(other_names)),
  arm_group_labels  TEXT CHECK (arm_group_labels IS NULL OR json_valid(arm_group_labels)),
  object_json       TEXT NOT NULL CHECK (json_valid(object_json)),
  PRIMARY KEY (nct_id, idx)
);

-- ===========================================================================
-- §11 REFRESH AND CHANGE DETECTION — a diff, not a monitor.
-- ===========================================================================

-- Raw layer: one row per fetch attempt, changed or not. Unchanged content is not
-- re-stored in raw_response (identical bodies are deduplicated); this log is where
-- every refresh's fetch metadata and high-water marks are appended. Append-only.
CREATE TABLE IF NOT EXISTS fetch_log (
  id              INTEGER PRIMARY KEY,
  run_id          INTEGER,                -- snapshot_run, when part of a refresh
  source          TEXT NOT NULL,
  endpoint        TEXT NOT NULL,
  request_params  TEXT NOT NULL,          -- canonical JSON
  fetched_at      TEXT NOT NULL,
  outcome         TEXT NOT NULL CHECK (outcome IN ('changed', 'unchanged', 'error')),
  raw_response_id INTEGER REFERENCES raw_response (id),
  content_sha256  TEXT,
  watermark       TEXT,                   -- high-water mark this fetch establishes (e.g. ctgov date)
  api_version     TEXT,
  note            TEXT
);
CREATE INDEX IF NOT EXISTS ix_fetch_log_src ON fetch_log (source, endpoint, fetched_at);

CREATE TRIGGER IF NOT EXISTS fetch_log_no_update BEFORE UPDATE ON fetch_log
BEGIN SELECT RAISE(ABORT, 'fetch_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS fetch_log_no_delete BEFORE DELETE ON fetch_log
BEGIN SELECT RAISE(ABORT, 'fetch_log is append-only'); END;

-- One row per refresh run, with the source versions it saw.
CREATE TABLE IF NOT EXISTS snapshot_run (
  run_id          INTEGER PRIMARY KEY,
  started_at      TEXT NOT NULL,
  finished_at     TEXT,
  status          TEXT NOT NULL CHECK (status IN ('running', 'complete', 'failed')),
  schema_version  INTEGER NOT NULL,
  code_version    TEXT,                   -- git commit, when known
  source_versions TEXT NOT NULL CHECK (json_valid(source_versions)),
  note            TEXT
);
CREATE TRIGGER IF NOT EXISTS snapshot_run_no_delete BEFORE DELETE ON snapshot_run
BEGIN SELECT RAISE(ABORT, 'snapshot history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS snapshot_run_close_once BEFORE UPDATE ON snapshot_run
WHEN OLD.status <> 'running'
BEGIN SELECT RAISE(ABORT, 'a finished snapshot run cannot be changed'); END;

-- Derived-view membership per run. Transitions are computed from this stored
-- state, so the map can show when a compound entered a cell and on what evidence.
-- No foreign keys: history must outlive rebuilds of the normalised layer.
CREATE TABLE IF NOT EXISTS snapshot_membership (
  run_id          INTEGER NOT NULL REFERENCES snapshot_run (run_id),
  cell            TEXT NOT NULL,
  cell_class      TEXT NOT NULL CHECK (cell_class IN ('derived_cell', 'churn')),
  subject         TEXT NOT NULL,          -- compound id, NCT id, 'compound:nct', or a source name
  compound_id     INTEGER,
  canonical_name  TEXT,
  entry_route     TEXT,
  evidence_tier   TEXT,
  nct_id          TEXT,
  state           TEXT,                   -- for state-valued cells (ITP tier, results_state)
  evidence        TEXT CHECK (evidence IS NULL OR json_valid(evidence)),
  PRIMARY KEY (run_id, cell, subject)
);
CREATE TRIGGER IF NOT EXISTS snapshot_membership_no_update BEFORE UPDATE ON snapshot_membership
BEGIN SELECT RAISE(ABORT, 'snapshot history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS snapshot_membership_no_delete BEFORE DELETE ON snapshot_membership
BEGIN SELECT RAISE(ABORT, 'snapshot history is append-only'); END;

-- Literature scan curation queue (SPEC §11.4). Never an entry route: no foreign key
-- to compound, no code path from here into compound, and nothing leaves 'queued'
-- without a named human.
CREATE TABLE IF NOT EXISTS literature_candidate (
  id                  INTEGER PRIMARY KEY,
  pmid                TEXT NOT NULL UNIQUE,
  title               TEXT NOT NULL,
  journal             TEXT,
  first_publication_date TEXT,
  query_version       TEXT NOT NULL,
  run_id              INTEGER,
  unmatched_chemicals TEXT NOT NULL CHECK (json_valid(unmatched_chemicals)
                        AND json_array_length(unmatched_chemicals) > 0),
  matched_chemicals   TEXT CHECK (matched_chemicals IS NULL OR json_valid(matched_chemicals)),
  raw_response_id     INTEGER REFERENCES raw_response (id),
  status              TEXT NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued', 'not_relevant', 'relevant_needs_curation', 'curated')),
  reviewed_by         TEXT CHECK (reviewed_by IS NULL OR (length(trim(reviewed_by)) > 0 AND
                        lower(trim(reviewed_by)) NOT IN ('auto', 'automatic', 'system', 'pipeline', 'script', 'default'))),
  reviewed_at         TEXT,
  note                TEXT,
  CHECK (status = 'queued' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
);

-- ---------------------------------------------------------------------------
-- Derived cells (SPEC §1 outputs). Built from the extension, harm and trial views.
-- ---------------------------------------------------------------------------

-- Systemic trials per compound (only systemic interventions count, §5.6).
DROP VIEW IF EXISTS v_compound_trials;
CREATE VIEW v_compound_trials AS
SELECT c.compound_id, c.canonical_name, c.entry_route, c.evidence_tier,
       count(DISTINCT ti.nct_id)                                                   AS n_systemic_trials,
       count(DISTINCT CASE WHEN o.ageing_adjacent = 1 THEN ti.nct_id END)           AS n_ageing_adjacent_trials,
       count(DISTINCT CASE WHEN t.results_state = 'NOT_POSTED_DUE' THEN ti.nct_id END) AS n_overdue_trials
FROM compound c
LEFT JOIN trial_intervention ti ON ti.compound_id = c.compound_id AND ti.systemic_exposure = 'systemic'
LEFT JOIN trial t               ON t.nct_id = ti.nct_id
LEFT JOIN trial_outcome o       ON o.nct_id = ti.nct_id
GROUP BY c.compound_id;

-- Replicated mammalian extension, direct or inherited through class (labelled).
DROP VIEW IF EXISTS v_extension_replicated;
CREATE VIEW v_extension_replicated AS
SELECT e.compound_id, e.canonical_name, e.entry_route, e.evidence_tier,
       NULL AS basis_compound_id, NULL AS basis_canonical_name, NULL AS basis_evidence_tier,
       e.itp_experiments, e.itp_cohorts_positive, e.itp_cohorts_total, e.itp_tier,
       e.n_mammal_extension_lab_groups
FROM v_extension_evidence e
WHERE e.has_mammal_extension AND e.replicated_mammal
UNION ALL
SELECT b.compound_id, b.canonical_name, b.entry_route, b.evidence_tier,
       min(b.basis_compound_id), group_concat(DISTINCT b.basis_canonical_name), 'measured_lifespan',
       max(e.itp_experiments), max(e.itp_cohorts_positive), max(e.itp_cohorts_total), max(e.itp_tier),
       max(e.n_mammal_extension_lab_groups)
FROM v_class_entry_basis b
JOIN v_extension_evidence e ON e.compound_id = b.basis_compound_id
                           AND e.has_mammal_extension AND e.replicated_mammal
WHERE b.entry_route = 'class'
GROUP BY b.compound_id;

DROP VIEW IF EXISTS v_gold_cell;
CREATE VIEW v_gold_cell AS
SELECT r.*, t.n_systemic_trials, t.n_ageing_adjacent_trials
FROM v_extension_replicated r JOIN v_compound_trials t USING (compound_id)
WHERE t.n_systemic_trials > 0;

DROP VIEW IF EXISTS v_untested_candidates;
CREATE VIEW v_untested_candidates AS
SELECT r.* FROM v_extension_replicated r JOIN v_compound_trials t USING (compound_id)
WHERE t.n_systemic_trials = 0;

DROP VIEW IF EXISTS v_under_tested;
CREATE VIEW v_under_tested AS
SELECT r.*, t.n_systemic_trials FROM v_extension_replicated r JOIN v_compound_trials t USING (compound_id)
WHERE t.n_ageing_adjacent_trials = 0;

DROP VIEW IF EXISTS v_null_cell;
CREATE VIEW v_null_cell AS
SELECT n.*, t.n_systemic_trials FROM v_itp_null n JOIN v_compound_trials t USING (compound_id)
WHERE t.n_systemic_trials > 0;

DROP VIEW IF EXISTS v_unreported;
CREATE VIEW v_unreported AS
SELECT c.compound_id, c.canonical_name, c.entry_route, c.evidence_tier,
       t.nct_id, t.status, t.completion_date, t.primary_completion_date, t.results_state
FROM trial t
JOIN trial_intervention ti ON ti.nct_id = t.nct_id AND ti.systemic_exposure = 'systemic'
JOIN compound c            ON c.compound_id = ti.compound_id
WHERE t.results_state = 'NOT_POSTED_DUE';

-- Reviews whose evidence no longer exists (e.g. the source corrected the row, so
-- its evidence_key changed). Never silently dropped: surfaced as a transition.
DROP VIEW IF EXISTS v_orphaned_reviews;
CREATE VIEW v_orphaned_reviews AS
SELECT 'direction_review' AS review_table, dr.evidence_key AS review_key, dr.reviewed_by, dr.reviewed_at
FROM direction_review dr
WHERE NOT EXISTS (SELECT 1 FROM animal_evidence ae WHERE ae.evidence_key = dr.evidence_key)
UNION ALL
SELECT 'itp_experiment_override', o.evidence_key, o.reviewed_by, o.reviewed_at
FROM itp_experiment_override o
WHERE NOT EXISTS (SELECT 1 FROM animal_evidence ae WHERE ae.evidence_key = o.evidence_key);

-- Live membership, the thing a run snapshots. Class 4 = derived_cell; classes 2-3 = churn.
-- (Class 1, new DrugAge compounds, comes from the raw CSV and is added by agesdk.refresh.)
DROP VIEW IF EXISTS v_cell_membership_live;
CREATE VIEW v_cell_membership_live AS
SELECT 'gold_cell' AS cell, 'derived_cell' AS cell_class, CAST(compound_id AS TEXT) AS subject,
       compound_id, canonical_name, entry_route, evidence_tier, NULL AS nct_id, NULL AS state,
       json_object('itp_cohorts', itp_cohorts_positive || '/' || itp_cohorts_total, 'itp_tier', itp_tier,
                   'itp_experiments', itp_experiments, 'mammal_lab_groups', n_mammal_extension_lab_groups,
                   'basis', basis_canonical_name, 'systemic_trials', n_systemic_trials) AS evidence
FROM v_gold_cell
UNION ALL
SELECT 'untested_candidate', 'derived_cell', CAST(compound_id AS TEXT), compound_id, canonical_name,
       entry_route, evidence_tier, NULL, NULL,
       json_object('itp_cohorts', itp_cohorts_positive || '/' || itp_cohorts_total, 'itp_tier', itp_tier,
                   'basis', basis_canonical_name)
FROM v_untested_candidates
UNION ALL
SELECT 'under_tested', 'derived_cell', CAST(compound_id AS TEXT), compound_id, canonical_name,
       entry_route, evidence_tier, NULL, NULL,
       json_object('systemic_trials', n_systemic_trials, 'itp_tier', itp_tier, 'basis', basis_canonical_name)
FROM v_under_tested
UNION ALL
SELECT 'null_cell', 'derived_cell', CAST(compound_id AS TEXT), compound_id, canonical_name,
       entry_route, evidence_tier, NULL, NULL,
       json_object('itp_cohorts', itp_cohorts_positive || '/' || itp_cohorts_total,
                   'itp_experiments', itp_experiments, 'systemic_trials', n_systemic_trials)
FROM v_null_cell
UNION ALL
SELECT 'harm_candidate', 'derived_cell', CAST(compound_id AS TEXT), compound_id, canonical_name,
       entry_route, evidence_tier, NULL, review_state,
       json_object('mammal_shortening_rows', n_mammal_shortening_rows, 'species', species,
                   'evidence_keys', json(current_evidence_keys))
FROM v_harm_candidates
UNION ALL
SELECT 'harm_signal', 'derived_cell', CAST(compound_id AS TEXT), compound_id, canonical_name,
       entry_route, evidence_tier, NULL, reviewed_by || ' ' || reviewed_at,
       json_object('exposure_basis', human_exposure_basis, 'reviewed_by', reviewed_by,
                   'reviewed_at', reviewed_at)
FROM v_harm_signal
UNION ALL
SELECT 'harm_review_stale', 'derived_cell', CAST(compound_id AS TEXT), compound_id, canonical_name,
       entry_route, evidence_tier, NULL, NULL,
       json_object('evidence_changed_since_review', evidence_changed_since_review,
                   'still_meets_threshold', still_meets_threshold, 'reviewed_by', reviewed_by)
FROM v_harm_signal
WHERE evidence_changed_since_review OR NOT still_meets_threshold
UNION ALL
SELECT 'unreported', 'derived_cell', CAST(compound_id AS TEXT), compound_id, canonical_name,
       entry_route, evidence_tier, NULL, NULL,
       json_object('overdue_trials', json_group_array(nct_id))
FROM v_unreported GROUP BY compound_id
UNION ALL
SELECT 'itp_tier', 'derived_cell', CAST(compound_id AS TEXT), compound_id, canonical_name,
       entry_route, evidence_tier, NULL, itp_tier,
       json_object('cohorts', itp_cohorts_positive || '/' || itp_cohorts_total,
                   'male', coalesce(itp_male_positive, 0) || '/' || itp_male_total,
                   'female', coalesce(itp_female_positive, 0) || '/' || itp_female_total,
                   'experiments', itp_experiments)
FROM v_itp_summary
UNION ALL
SELECT 'mechanistic_dossier', 'derived_cell', CAST(compound_id AS TEXT), compound_id, canonical_name,
       entry_route, evidence_tier, NULL, NULL,
       json_object('cocktails', cocktails, 'citations', citations, 'systemic_trials', n_systemic_trials)
FROM v_mechanistic_human_dossier
UNION ALL
SELECT 'orphaned_review', 'derived_cell', review_table || ':' || review_key, NULL, NULL, NULL, NULL, NULL, NULL,
       json_object('review_table', review_table, 'reviewed_by', reviewed_by, 'reviewed_at', reviewed_at)
FROM v_orphaned_reviews
UNION ALL
SELECT 'compound_trial', 'churn', ti.compound_id || ':' || ti.nct_id, ti.compound_id, c.canonical_name,
       c.entry_route, c.evidence_tier, ti.nct_id, NULL, NULL
FROM trial_intervention ti JOIN compound c ON c.compound_id = ti.compound_id
WHERE ti.systemic_exposure = 'systemic'
GROUP BY ti.compound_id, ti.nct_id
UNION ALL
SELECT 'trial_state', 'churn', t.nct_id, NULL, NULL, NULL, NULL, t.nct_id, t.results_state, NULL
FROM trial t;

-- Every change between consecutive completed runs: entered / left / state_changed.
-- The full log, churn included. The first run is a baseline and has no changes.
DROP VIEW IF EXISTS v_membership_changes;
CREATE VIEW v_membership_changes AS
WITH runs AS (
  SELECT run_id, finished_at, lag(run_id) OVER (ORDER BY run_id) AS prev_run_id
  FROM snapshot_run WHERE status = 'complete')
SELECT r.run_id, r.prev_run_id, r.finished_at, m.cell, m.cell_class, m.subject, 'entered' AS change,
       m.compound_id, m.canonical_name, m.entry_route, m.evidence_tier, m.nct_id,
       NULL AS old_state, m.state AS new_state, NULL AS old_evidence, m.evidence AS new_evidence
FROM runs r JOIN snapshot_membership m ON m.run_id = r.run_id
WHERE r.prev_run_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM snapshot_membership p
                  WHERE p.run_id = r.prev_run_id AND p.cell = m.cell AND p.subject = m.subject)
UNION ALL
SELECT r.run_id, r.prev_run_id, r.finished_at, p.cell, p.cell_class, p.subject, 'left',
       p.compound_id, p.canonical_name, p.entry_route, p.evidence_tier, p.nct_id,
       p.state, NULL, p.evidence, NULL
FROM runs r JOIN snapshot_membership p ON p.run_id = r.prev_run_id
WHERE NOT EXISTS (SELECT 1 FROM snapshot_membership m
                  WHERE m.run_id = r.run_id AND m.cell = p.cell AND m.subject = p.subject)
UNION ALL
SELECT r.run_id, r.prev_run_id, r.finished_at, m.cell, m.cell_class, m.subject, 'state_changed',
       m.compound_id, m.canonical_name, m.entry_route, m.evidence_tier, m.nct_id,
       p.state, m.state, p.evidence, m.evidence
FROM runs r
JOIN snapshot_membership m ON m.run_id = r.run_id
JOIN snapshot_membership p ON p.run_id = r.prev_run_id AND p.cell = m.cell AND p.subject = m.subject
WHERE p.state IS NOT m.state;

-- What warrants attention (change class 4). Everything else stays in the log.
DROP VIEW IF EXISTS v_cell_transitions;
CREATE VIEW v_cell_transitions AS
SELECT * FROM (
  SELECT CASE
           WHEN cell = 'gold_cell'         AND change = 'entered' THEN 'entered_gold_cell'
           WHEN cell = 'under_tested'      AND change = 'left'    THEN 'left_under_tested'
           WHEN cell = 'harm_candidate'    AND change = 'entered' THEN 'new_harm_candidate'
           WHEN cell = 'unreported'        AND change = 'entered' THEN 'results_now_overdue'
           WHEN cell = 'itp_tier'                                 THEN 'itp_tier_changed'
           WHEN cell = 'harm_review_stale' AND change = 'entered' THEN 'harm_review_needs_revisit'
           WHEN cell = 'orphaned_review'   AND change = 'entered' THEN 'review_orphaned'
         END AS transition,
         run_id, prev_run_id, finished_at, cell, change, subject, compound_id, canonical_name,
         entry_route, evidence_tier, old_state, new_state, old_evidence, new_evidence
  FROM v_membership_changes WHERE cell_class = 'derived_cell')
WHERE transition IS NOT NULL;

PRAGMA user_version = 7;
