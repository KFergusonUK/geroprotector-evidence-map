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
REQUIRED = ("key", "canonical_name", "group", "role", "expected_entry_route", "expected_itp",
            "headline_v1", "pubchem_cid", "inchikey", "chembl_id", "atc_codes",
            "drugage_names", "must_match", "must_not_match", "needs_review", "review")
ENTRY_ROUTES = {"direct", "class", "excluded"}
ITP_STATES = {"positive", "null_result", "untested"}
ROLES = {"seed", "class_test_case"}


def load(path: Path = FIXTURE_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate(fx: dict) -> list[str]:
    """Internal consistency. Returns a list of problems (empty = valid)."""
    errs: list[str] = []
    seen: dict[str, dict] = {"key": {}, "pubchem_cid": {}, "inchikey": {}, "canonical_name": {}}
    must_match_owner: dict[str, str] = {}

    for c in fx.get("compounds", []):
        k = c.get("key", "<no key>")
        for field in REQUIRED:
            if field not in c:
                errs.append(f"{k}: missing field {field}")
        if errs and errs[-1].startswith(f"{k}: missing"):
            continue
        if not isinstance(c["inchikey"], str) or not INCHIKEY_RE.match(c["inchikey"]):
            errs.append(f"{k}: inchikey must be a full 27-char InChIKey, got {c['inchikey']!r}")
        if c["canonical_name"] != c["canonical_name"].strip() or not c["canonical_name"].isascii():
            errs.append(f"{k}: canonical_name must be trimmed ASCII")
        if c["expected_entry_route"] not in ENTRY_ROUTES:
            errs.append(f"{k}: bad expected_entry_route {c['expected_entry_route']!r}")
        if c["expected_itp"] not in ITP_STATES:
            errs.append(f"{k}: bad expected_itp {c['expected_itp']!r}")
        if c["role"] not in ROLES:
            errs.append(f"{k}: bad role {c['role']!r}")
        if c["atc_codes"] is not None:
            for code in c["atc_codes"]:
                if not ATC_RE.match(code):
                    errs.append(f"{k}: bad ATC code {code!r}")

        # Direct entry ⇔ the compound is in DrugAge.
        if (c["expected_entry_route"] == "direct") != bool(c["drugage_names"]):
            errs.append(f"{k}: expected_entry_route={c['expected_entry_route']} "
                        f"but drugage_names={c['drugage_names']!r}")
        if c["expected_entry_route"] != "direct" and c["role"] == "seed":
            errs.append(f"{k}: seeds must enter directly")

        for field in seen:
            v = c[field]
            if v in seen[field]:
                errs.append(f"{k}: duplicate {field} {v!r} (also {seen[field][v]})")
            seen[field][v] = k

        mm, mn, nr = (set(map(str, c[f])) for f in ("must_match", "must_not_match", "needs_review"))
        for a, b, label in ((mm, mn, "must_match/must_not_match"),
                            (mm, nr, "must_match/needs_review"),
                            (mn, nr, "must_not_match/needs_review")):
            if a & b:
                errs.append(f"{k}: {label} overlap: {sorted(a & b)}")
        for s in mm:
            if s in must_match_owner and must_match_owner[s] != k:
                errs.append(f"{k}: must_match {s!r} also must_match for {must_match_owner[s]}")
            must_match_owner[s] = k
        for s in c.get("drugage_names", []):
            if s not in mm:
                errs.append(f"{k}: DrugAge name {s!r} is not in must_match")

    # A string one compound must match must not be something another compound must reject
    # unless that is deliberate — it always is a precision test, so only flag self-conflicts above.
    return errs


def load_species_tiers(path: Path = SPECIES_PATH) -> dict[str, str]:
    with open(path, encoding="utf-8", newline="") as fh:
        return {r["species"]: r["tier"] for r in csv.DictReader(fh)}


def drugage_facts(rows: list[dict], names: list[str], tiers: dict[str, str]) -> dict:
    """What DrugAge actually says about the given exact names."""
    sel = [r for r in rows if r["compound_name"] in names]
    itp = [r for r in sel if r["ITP"] == "Yes"]

    def sig_extension(r):
        try:
            return r["avg_lifespan_significance"] == "S" and float(r["avg_lifespan_change_percent"]) > 0
        except ValueError:
            return False

    if not itp:
        itp_state = "untested"
    elif any(sig_extension(r) for r in itp):
        itp_state = "positive"
    else:
        itp_state = "null_result"
    return {
        "n_rows": len(sel),
        "names_found": sorted({r["compound_name"] for r in sel}),
        "itp": itp_state,
        "mammal": any(tiers.get(r["species"]) == "mammal" for r in sel),
    }


def check_against_drugage(fx: dict, rows: list[dict], tiers: dict[str, str]) -> list[str]:
    errs = []
    all_names = {r["compound_name"] for r in rows}
    for c in fx["compounds"]:
        k = c["key"]
        for n in c["drugage_names"] + c.get("drugage_names_needs_review", []):
            if n not in all_names:
                errs.append(f"{k}: DrugAge name {n!r} not found in the loaded CSV")
        if not c["drugage_names"]:
            continue
        facts = drugage_facts(rows, c["drugage_names"], tiers)
        if facts["itp"] != c["expected_itp"]:
            errs.append(f"{k}: fixture says ITP {c['expected_itp']}, DrugAge says {facts['itp']}")
        if facts["mammal"] != c["headline_v1"]:
            errs.append(f"{k}: fixture headline_v1={c['headline_v1']}, DrugAge mammal={facts['mammal']}")
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
