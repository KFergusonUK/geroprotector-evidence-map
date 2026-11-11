"""Hand-curated reference data that lives in the repo (data/reference/)."""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from datetime import date

import yaml

from agesdk.db import PROJECT_ROOT

SPECIES_PATH = PROJECT_ROOT / "data" / "reference" / "species_taxon.csv"
REPROGRAMMING_PATH = PROJECT_ROOT / "data" / "reference" / "reprogramming_evidence.yaml"

INCHIKEY_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
TIERS = {"measured_lifespan", "inherited_class", "mechanistic_only"}
RECORDED_BY = "Claude (AI-assisted extraction from full text; awaiting human review)"


def load_species(conn: sqlite3.Connection, path=SPECIES_PATH) -> int:
    """Upsert data/reference/species_taxon.csv into species_taxon. Idempotent."""
    with open(path, encoding="utf-8", newline="") as fh:
        rows = [(r["species"], r["tier"], r.get("ncbi_taxid") or None, r.get("note") or None)
                for r in csv.DictReader(fh)]
    conn.executemany(
        """INSERT INTO species_taxon (species, tier, ncbi_taxid, note) VALUES (?, ?, ?, ?)
           ON CONFLICT (species) DO UPDATE SET tier = excluded.tier,
             ncbi_taxid = excluded.ncbi_taxid, note = excluded.note""", rows)
    conn.commit()
    return len(rows)


# ---------------------------------------------------------------- reprogramming

def load_reprogramming_spec(path=REPROGRAMMING_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate_reprogramming(spec: dict) -> list[str]:
    """File-level checks; the schema re-checks the per-row rules on load."""
    errs: list[str] = []
    cits = spec.get("citations", {})
    comps = {c["key"]: c for c in spec.get("compounds", [])}
    for key, c in cits.items():
        if not (c.get("pmid") or c.get("doi")):
            errs.append(f"citation {key}: needs a PMID or DOI")
        if c.get("verified_from") not in ("full_text", "abstract"):
            errs.append(f"citation {key}: verified_from must be full_text or abstract")
    for ck in spec.get("cocktails", []):
        name = ck.get("name", "<unnamed>")
        if ck.get("citation") not in cits:
            errs.append(f"{name}: unknown citation {ck.get('citation')!r}")
        for field in ("cell_type", "cell_species", "demonstration_kind", "demonstrated",
                      "components_as_written", "component_keys"):
            if not ck.get(field):
                errs.append(f"{name}: missing {field}")
        if len(ck.get("components_as_written") or []) < 2:
            errs.append(f"{name}: a cocktail needs at least two components")
        if len(ck.get("component_keys") or []) != len(ck.get("components_as_written") or []):
            errs.append(f"{name}: component_keys and components_as_written differ in length")
        for k in ck.get("component_keys") or []:
            if k not in comps:
                errs.append(f"{name}: unknown component key {k!r}")
    seen_keys = set()
    for c in comps.values():
        k = c["key"]
        if c.get("expected_evidence_tier") not in TIERS:
            errs.append(f"{k}: bad expected_evidence_tier")
        if c.get("identity_status") == "verified":
            if not (isinstance(c.get("inchikey"), str) and INCHIKEY_RE.match(c["inchikey"])):
                errs.append(f"{k}: verified identity needs a full 27-char InChIKey")
            if c["inchikey"] in seen_keys:
                errs.append(f"{k}: duplicate InChIKey")
            seen_keys.add(c["inchikey"])
        elif c.get("identity_status") != "needs_review":
            errs.append(f"{k}: identity_status must be verified or needs_review")
        if bool(c.get("drugage_names")) != (c.get("expected_evidence_tier") == "measured_lifespan"):
            errs.append(f"{k}: in DrugAge <=> measured_lifespan")
        overlap = set(c.get("names_in_sources", [])) & set(c.get("must_not_match", []))
        if overlap:
            errs.append(f"{k}: names_in_sources/must_not_match overlap {sorted(overlap)}")
    return errs


def check_reprogramming_vs_drugage(spec: dict, drugage_rows: list[dict]) -> list[str]:
    """A compound in DrugAge must be graded measured_lifespan; one claimed mechanistic_only
    must not be in DrugAge under any of its names (case-insensitive)."""
    errs = []
    names = {r["compound_name"] for r in drugage_rows}
    lower = {n.strip().lower() for n in names}
    for c in spec["compounds"]:
        for n in c.get("drugage_names", []):
            if n not in names:
                errs.append(f"{c['key']}: DrugAge name {n!r} not in the loaded CSV")
        if c["expected_evidence_tier"] == "mechanistic_only":
            hits = [n for n in c.get("names_in_sources", []) + [c["canonical_name"]]
                    if n.strip().lower() in lower]
            if hits:
                errs.append(f"{c['key']}: claimed mechanistic_only but DrugAge has {hits}")
    return errs


def load_reprogramming(conn: sqlite3.Connection, spec: dict | None = None,
                       recorded_at: str | None = None) -> dict:
    """Load verified reprogramming evidence. Idempotent.

    - mechanistic_only compounds are created (entry_route 'reprogramming_cocktail') if absent;
    - measured_lifespan compounds are linked only if already loaded from DrugAge;
    - needs_review identities are never loaded.
    """
    spec = spec or load_reprogramming_spec()
    errs = validate_reprogramming(spec)
    if errs:
        raise ValueError("reprogramming_evidence.yaml invalid:\n  " + "\n  ".join(errs))
    recorded_at = recorded_at or date.today().isoformat()
    comps = {c["key"]: c for c in spec["compounds"]}
    report = {"created": [], "linked": [], "skipped_needs_review": [], "skipped_not_loaded": [],
              "rows_inserted": 0}
    ids: dict[str, int] = {}
    for k, c in comps.items():
        if c["identity_status"] != "verified":
            report["skipped_needs_review"].append(k)
            continue
        row = conn.execute("SELECT compound_id FROM compound WHERE inchikey = ?", (c["inchikey"],)).fetchone()
        if row:
            ids[k] = row[0]
            report["linked"].append(k)
        elif c["expected_evidence_tier"] == "mechanistic_only":
            ids[k] = conn.execute(
                "INSERT INTO compound (canonical_name, pubchem_cid, inchikey, entry_route, evidence_tier, notes) "
                "VALUES (?, ?, ?, 'reprogramming_cocktail', 'mechanistic_only', ?)",
                (c["canonical_name"], c["pubchem_cid"], c["inchikey"], c.get("note"))).lastrowid
            report["created"].append(k)
        else:
            report["skipped_not_loaded"].append(k)

    for ck in spec["cocktails"]:
        cit = spec["citations"][ck["citation"]]
        for comp_key, as_written in zip(ck["component_keys"], ck["components_as_written"]):
            if comp_key not in ids:
                continue
            cur = conn.execute(
                """INSERT OR IGNORE INTO reprogramming_evidence (
                     compound_id, source_component_name, citation_pmid, citation_doi,
                     cocktail_name, cocktail_components, composition_complete,
                     cell_type, cell_species, in_vivo, demonstration_kind, demonstrated,
                     verified_from, recorded_by, recorded_at, reviewed_by, reviewed_at, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ids[comp_key], as_written, cit.get("pmid"), cit.get("doi"),
                 ck["name"], json.dumps(ck["components_as_written"], ensure_ascii=False),
                 int(ck["composition_complete"]), ck["cell_type"], ck["cell_species"],
                 int(ck["in_vivo"]), ck["demonstration_kind"], " ".join(ck["demonstrated"].split()),
                 cit["verified_from"], RECORDED_BY, recorded_at,
                 ck.get("reviewed_by"), ck.get("reviewed_at"), ck.get("note")))
            report["rows_inserted"] += cur.rowcount
    conn.commit()
    return report
