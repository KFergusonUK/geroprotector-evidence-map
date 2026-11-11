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
  -- 'direct': has animal lifespan evidence itself.
  -- 'class' : enters only because it shares an ATC level-4 class with a
  --           'direct' compound. Weaker, one-hop inference. Never merge the two in output.
  entry_route     TEXT NOT NULL CHECK (entry_route IN ('direct', 'class')),
  notes           TEXT
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
  --   auto           — compound has exactly one level-4 class, and it is not an 'other' (…X) bucket
  --   pending_review — multi-class compound, or an 'other' bucket; blocks class entry until reviewed
  --   accepted / rejected — a human decision on whether this class may carry class entry
  review_status   TEXT NOT NULL DEFAULT 'pending_review'
                    CHECK (review_status IN ('auto', 'pending_review', 'accepted', 'rejected')),
  reviewed_by     TEXT,
  reviewed_at     TEXT,
  note            TEXT,
  PRIMARY KEY (compound_id, atc_code),
  CHECK (review_status NOT IN ('accepted', 'rejected') OR reviewed_by IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS ix_compound_atc_l4 ON compound_atc (atc_level4);

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
  is_itp                    INTEGER NOT NULL DEFAULT 0 CHECK (is_itp IN (0, 1)),
  pmid                      TEXT,           -- joins publication.pmid; no FK, publications load later
  source                    TEXT NOT NULL DEFAULT 'drugage',
  source_compound_name      TEXT NOT NULL,  -- verbatim source string, unmodified
  raw_response_id           INTEGER REFERENCES raw_response (id),
  source_row_number         INTEGER,        -- 1-based data row within that raw response
  UNIQUE (raw_response_id, source_row_number)
);

CREATE INDEX IF NOT EXISTS ix_animal_evidence_compound ON animal_evidence (compound_id);

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
  PRIMARY KEY (nct_id, raw_name)
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

-- Compounds whose ATC rows need a human decision before they can carry class entry.
DROP VIEW IF EXISTS v_atc_review_needed;
CREATE VIEW v_atc_review_needed AS
WITH per_compound AS (
  SELECT compound_id, count(DISTINCT atc_level4) AS n_level4
  FROM compound_atc GROUP BY compound_id)
SELECT c.compound_id, c.canonical_name, c.entry_route,
       ca.atc_code, ca.atc_level4, ca.review_status, pc.n_level4,
       CASE
         WHEN pc.n_level4 > 1 AND substr(ca.atc_level4, 5, 1) = 'X' THEN 'multi_class+other_bucket'
         WHEN pc.n_level4 > 1 THEN 'multi_class'
         WHEN substr(ca.atc_level4, 5, 1) = 'X' THEN 'other_bucket'
       END AS reason
FROM compound_atc ca
JOIN compound c ON c.compound_id = ca.compound_id
JOIN per_compound pc ON pc.compound_id = ca.compound_id
WHERE (pc.n_level4 > 1 OR substr(ca.atc_level4, 5, 1) = 'X')
  AND ca.review_status NOT IN ('accepted', 'rejected');

-- Why each compound is eligible via class: one hop only, from a 'direct'
-- compound with animal evidence, through a class both sides may use.
DROP VIEW IF EXISTS v_class_entry_basis;
CREATE VIEW v_class_entry_basis AS
SELECT DISTINCT
  c.compound_id, c.canonical_name, c.entry_route,
  ca.atc_level4,
  b.compound_id    AS basis_compound_id,
  b.canonical_name AS basis_canonical_name
FROM compound c
JOIN compound_atc ca ON ca.compound_id = c.compound_id
                    AND ca.review_status IN ('auto', 'accepted')
JOIN compound_atc ba ON ba.atc_level4 = ca.atc_level4
                    AND ba.compound_id <> c.compound_id
                    AND ba.review_status IN ('auto', 'accepted')
JOIN compound b      ON b.compound_id = ba.compound_id
                    AND b.entry_route = 'direct'
WHERE EXISTS (SELECT 1 FROM animal_evidence ae WHERE ae.compound_id = b.compound_id);

-- Integrity check: stored entry_route vs what the data supports. Should be empty.
DROP VIEW IF EXISTS v_entry_route_check;
CREATE VIEW v_entry_route_check AS
SELECT c.compound_id, c.canonical_name, c.entry_route,
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
       END AS problem
FROM compound c
WHERE problem IS NOT NULL;

PRAGMA user_version = 1;
