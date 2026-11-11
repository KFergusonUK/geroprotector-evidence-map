"""Seed compound fixture: load, validate, and check against the raw layer.

The fixture is hand-resolved ground truth (SPEC §7 step 1). These checks keep it
honest: internal consistency, agreement with DrugAge as actually downloaded, and
agreement with PubChem lookups (all of which go through the raw-layer cache).
"""
from __future__ import annotations

import csv
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

import yaml

from agesdk.db import PROJECT_ROOT

FIXTURE_PATH = PROJECT_ROOT / "data" / "fixtures" / "seed_compounds.yaml"
SPECIES_PATH = PROJECT_ROOT / "data" / "reference" / "species_taxon.csv"

INCHIKEY_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
ATC_RE = re.compile(r"^[A-Z]\d\d[A-Z][A-Z]\d\d$")
REQUIRED = ("key", "canonical_name", "group", "role", "expected_entry_route", "expected_paths",
            "itp", "mammal_evidence", "mammal_extension", "pubchem_cid", "inchikey",
            "chembl_id", "atc_codes", "drugage_names", "must_match", "must_not_match",
            "needs_review", "route_excluded", "decisions", "review")
ENTRY_ROUTES = {"direct", "class", "excluded"}
PATHS = {"extension", "harm_candidate"}
ROLES = {"seed", "class_test_case", "linked_compound"}


def load(path: Path = FIXTURE_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


TIERS = {"none", "weak", "mixed", "strong"}
ITP_KEYS = {"experiments", "arms", "cohorts", "male", "female", "tier"}


def _check_itp(k: str, itp, errs: list[str]) -> None:
    if itp == "untested":
        return
    if not isinstance(itp, dict) or set(itp) != ITP_KEYS:
        errs.append(f'{k}: itp must be "untested" or have {sorted(ITP_KEYS)}')
        return
    for field in ("arms", "cohorts", "male", "female"):
        pos, tot = itp[field]
        if not (isinstance(pos, int) and isinstance(tot, int) and 0 <= pos <= tot):
            errs.append(f"{k}: bad ITP {field} ratio {pos}/{tot}")
    if itp["male"][1] + itp["female"][1] > itp["cohorts"][1]:
        errs.append(f"{k}: ITP male+female cohorts exceed total cohorts")
    if not (itp["experiments"] <= itp["cohorts"][1] <= itp["arms"][1]):
        errs.append(f"{k}: ITP units out of order: need experiments <= cohorts <= arms")
    if set(itp["tier"]) != {"overall", "male", "female"} or not set(itp["tier"].values()) <= TIERS:
        errs.append(f"{k}: bad ITP tier {itp['tier']!r}")


def validate(fx: dict) -> list[str]:
    """Internal consistency. Returns a list of problems (empty = valid)."""
    errs: list[str] = []
    seen: dict[str, dict] = {"key": {}, "pubchem_cid": {}, "inchikey": {}, "canonical_name": {}}
    must_match_owner: dict[str, str] = {}
    keys = {c.get("key") for c in fx.get("compounds", [])}
    entries = {c.get("key"): c for c in fx.get("compounds", [])}

    for c in fx.get("compounds", []):
        k = c.get("key", "<no key>")
        missing = [f for f in REQUIRED if f not in c]
        if missing:
            errs.append(f"{k}: missing fields {missing}")
            continue
        if not isinstance(c["inchikey"], str) or not INCHIKEY_RE.match(c["inchikey"]):
            errs.append(f"{k}: inchikey must be a full 27-char InChIKey, got {c['inchikey']!r}")
        if c["canonical_name"] != c["canonical_name"].strip() or not c["canonical_name"].isascii():
            errs.append(f"{k}: canonical_name must be trimmed ASCII")
        if c["expected_entry_route"] not in ENTRY_ROUTES:
            errs.append(f"{k}: bad expected_entry_route {c['expected_entry_route']!r}")
        if c["role"] not in ROLES:
            errs.append(f"{k}: bad role {c['role']!r}")
        if not set(c["expected_paths"]) <= PATHS:
            errs.append(f"{k}: bad expected_paths {c['expected_paths']!r}")
        _check_itp(k, c["itp"], errs)
        if c["mammal_extension"] and not c["mammal_evidence"]:
            errs.append(f"{k}: mammal_extension without mammal_evidence")
        if "harm_candidate" in c["expected_paths"] and not c["mammal_evidence"]:
            errs.append(f"{k}: harm_candidate requires mammal evidence")
        if c["atc_codes"] is not None:
            for code in c["atc_codes"]:
                if not ATC_RE.match(code):
                    errs.append(f"{k}: bad ATC code {code!r}")
        for d in c["decisions"]:
            if not all(d.get(f) for f in ("decision", "decided_by", "decided_at")):
                errs.append(f"{k}: decision needs decision, decided_by, decided_at: {d!r}")

        # Direct entry ⇔ the compound is in DrugAge. Paths need DrugAge evidence.
        if (c["expected_entry_route"] == "direct") != bool(c["drugage_names"]):
            errs.append(f"{k}: expected_entry_route={c['expected_entry_route']} "
                        f"but drugage_names={c['drugage_names']!r}")
        if c["expected_paths"] and not c["drugage_names"]:
            errs.append(f"{k}: expected_paths without DrugAge evidence")
        if c["role"] == "seed" and c["expected_entry_route"] != "direct":
            errs.append(f"{k}: seeds must enter directly")

        # same_substance_as: must name another entry, reciprocally.
        other = c.get("same_substance_as")
        if other is not None:
            if other not in keys or other == k:
                errs.append(f"{k}: same_substance_as {other!r} is not another fixture entry")
            elif entries[other].get("same_substance_as") != k:
                errs.append(f"{k}: same_substance_as {other!r} is not reciprocated")
            elif entries[other]["inchikey"] == c["inchikey"]:
                errs.append(f"{k}: same_substance_as link with identical InChIKey; that is a duplicate")

        for field in seen:
            v = c[field]
            if v in seen[field]:
                errs.append(f"{k}: duplicate {field} {v!r} (also {seen[field][v]})")
            seen[field][v] = k

        mm, mn, nr, rx = (set(map(str, c[f])) for f in
                          ("must_match", "must_not_match", "needs_review", "route_excluded"))
        for a, b, label in ((mm, mn, "must_match/must_not_match"),
                            (mm, nr, "must_match/needs_review"),
                            (mn, nr, "must_not_match/needs_review"),
                            (rx, mn, "route_excluded/must_not_match"),
                            (rx, nr, "route_excluded/needs_review")):
            if a & b:
                errs.append(f"{k}: {label} overlap: {sorted(a & b)}")
        for s in mm:
            if s in must_match_owner and must_match_owner[s] != k:
                errs.append(f"{k}: must_match {s!r} also must_match for {must_match_owner[s]}")
            must_match_owner[s] = k
        for s in c.get("drugage_names", []):
            if s not in mm:
                errs.append(f"{k}: DrugAge name {s!r} is not in must_match")
    return errs


def load_species_tiers(path: Path = SPECIES_PATH) -> dict[str, str]:
    with open(path, encoding="utf-8", newline="") as fh:
        return {r["species"]: r["tier"] for r in csv.DictReader(fh)}


def build_seed_db(fx: dict, raw_id: int, rows: list[dict]) -> sqlite3.Connection:
    """In-memory database holding the fixture's direct compounds and their real
    DrugAge rows, so expectations are checked by the production SQL views rather
    than by a second implementation of the same rules."""
    from agesdk import db, normalise, reference
    conn = db.connect(":memory:")
    db.init_db(conn)
    reference.load_species(conn)
    conn.execute("INSERT INTO raw_response (id, source, endpoint, request_params, response_body, "
                 "fetched_at, content_sha256) VALUES (?, 'drugage', 'fixture-check', '{}', '', '', '')",
                 (raw_id,))
    ids: dict[str, int] = {}
    for c in fx["compounds"]:
        if c["drugage_names"]:
            cid = conn.execute("INSERT INTO compound (canonical_name, entry_route, evidence_tier, inchikey) "
                               "VALUES (?, 'direct', 'measured_lifespan', ?)",
                               (c["canonical_name"], c["inchikey"])).lastrowid
            ids.update({n: cid for n in c["drugage_names"]})
    normalise.load_drugage_evidence(conn, raw_id, rows, ids)
    return conn


def facts_from_views(conn: sqlite3.Connection, canonical_name: str) -> dict:
    one = lambda sql: conn.execute(sql, (canonical_name,)).fetchone()
    paths = []
    if one("SELECT 1 FROM v_extension_evidence WHERE canonical_name = ?"):
        paths.append("extension")
    if one("SELECT 1 FROM v_harm_candidates WHERE canonical_name = ?"):
        paths.append("harm_candidate")
    i = one("SELECT * FROM v_itp_summary WHERE canonical_name = ?")
    itp = "untested" if i is None else {
        "experiments": i["itp_experiments"],
        "arms": [i["itp_arms_positive"], i["itp_arms_total"]],
        "cohorts": [i["itp_cohorts_positive"], i["itp_cohorts_total"]],
        "male": [i["itp_male_positive"] or 0, i["itp_male_total"]],
        "female": [i["itp_female_positive"] or 0, i["itp_female_total"]],
        "tier": {"overall": i["itp_tier"], "male": i["itp_male_tier"], "female": i["itp_female_tier"]},
    }
    mammal = conn.execute("""SELECT count(*) AS n, coalesce(sum(effective_direction = 'extension'), 0) AS ext
                             FROM v_evidence_counted v JOIN compound c USING (compound_id)
                             WHERE c.canonical_name = ? AND v.tier = 'mammal'""",
                          (canonical_name,)).fetchone()
    return {"paths": paths, "itp": itp,
            "mammal_evidence": mammal["n"] > 0, "mammal_extension": mammal["ext"] > 0}


def check_against_drugage(fx: dict, raw_id: int, rows: list[dict]) -> list[str]:
    errs = []
    all_names = {r["compound_name"] for r in rows}
    conn = build_seed_db(fx, raw_id, rows)
    for c in fx["compounds"]:
        k = c["key"]
        for n in c["drugage_names"] + c.get("drugage_names_needs_review", []):
            if n not in all_names:
                errs.append(f"{k}: DrugAge name {n!r} not found in the loaded CSV")
        facts = facts_from_views(conn, c["canonical_name"])
        for field, expected in (("paths", c["expected_paths"]), ("itp", c["itp"]),
                                ("mammal_evidence", c["mammal_evidence"]),
                                ("mammal_extension", c["mammal_extension"])):
            if facts[field] != expected:
                errs.append(f"{k}: fixture {field}={expected!r}, views say {facts[field]!r}")
    return errs


def check_against_pubchem(fx: dict, conn: sqlite3.Connection) -> list[str]:
    """Each fixture CID's InChIKey must equal the fixture InChIKey (cached lookups)."""
    from agesdk.sources import pubchem
    f = pubchem.fetcher(conn)
    errs = []
    for c in fx["compounds"]:
        props = pubchem.properties(f, c["pubchem_cid"])
        if props is None:
            errs.append(f"{c['key']}: PubChem CID {c['pubchem_cid']} not found")
        elif props["InChIKey"] != c["inchikey"]:
            errs.append(f"{c['key']}: PubChem CID {c['pubchem_cid']} has InChIKey "
                        f"{props['InChIKey']}, fixture has {c['inchikey']}")
    return errs


def chembl_report(fx: dict, conn: sqlite3.Connection) -> list[dict]:
    """Look up each fixture InChIKey in ChEMBL; report IDs and ATC codes for hand entry.

    Deliberately does not write to the fixture: the values are copied in by hand
    after review, so the fixture stays a reviewed artefact rather than a cache.
    """
    from agesdk.sources import chembl
    f = chembl.fetcher(conn)
    out = []
    for c in fx["compounds"]:
        mols = chembl.molecules_by_inchikey(f, c["inchikey"])
        out.append({
            "key": c["key"],
            "inchikey": c["inchikey"],
            "matches": [{"chembl_id": m["molecule_chembl_id"], "pref_name": m.get("pref_name"),
                         "parent": chembl.parent_chembl_id(m), "atc": chembl.atc_codes(m)}
                        for m in mols],
        })
    return out


def atc_class_index(fx: dict) -> dict[str, list[str]]:
    """level-4 ATC class -> fixture keys, once ATC codes are filled in."""
    idx: dict[str, list[str]] = defaultdict(list)
    for c in fx["compounds"]:
        for code in c["atc_codes"] or []:
            idx[code[:5]].append(c["key"])
    return dict(idx)
