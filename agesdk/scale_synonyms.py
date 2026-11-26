"""Stage 2 of the scaled synonym pipeline (docs/synonym_pipeline.md): identity -> synonyms.

Input: data/scale/identity.csv (stage 1), outcome 'resolved' only; 'needs_check' entries
wait for Kevin's decisions. Cache-first: every ChEMBL and PubChem lookup goes through the
raw layer. Output, nothing else:
  data/scale/synonyms.csv          every candidate string, its sources, and its fate
  data/scale/scaled_compounds.yaml  fixture-shaped entries for the resolver (not yet wired in)

Decided (Kevin Ferguson, 2026-11-26): D1 query strings = DrugAge names + ChEMBL preferred
name + ChEMBL INN/USAN/BAN/JAN/trade names; D2 no fuzzy for scaled compounds; D3 no
hand negatives, but a string generated for two compounds (or equal to any seed fixture
string) never auto-accepts: it goes to review for every compound involved. "Equal" is
judged under the resolver's own normalise() and strip() forms.
"""
from __future__ import annotations

import csv
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from agesdk import fixture
from agesdk.db import PROJECT_ROOT
from agesdk.raw import HttpError
from agesdk.resolver import Resolver
from agesdk.sources import chembl, pubchem

RULES_PATH = PROJECT_ROOT / "data" / "rules" / "synonyms.yaml"
SCALE = PROJECT_ROOT / "data" / "scale"


def load_rules() -> dict:
    return yaml.safe_load(open(RULES_PATH, encoding="utf-8"))


class PubchemFilter:
    def __init__(self, rules: dict):
        self.drop = {k: re.compile(v, re.IGNORECASE) for k, v in rules["pubchem_drop_patterns"].items()}
        self.strip_bracket = re.compile(rules["pubchem_strip_trailing_bracket"])
        self.min_len, self.max_len = rules["pubchem_min_len"], rules["pubchem_max_len"]
        self.words = set()
        for p in rules["dictionary_files"]:
            if Path(p).exists():
                self.words |= {w.strip().lower() for w in open(p, encoding="utf-8", errors="ignore")}

    def __call__(self, s: str) -> tuple[str | None, str | None]:
        """(kept string, None) or (None, drop reason)."""
        t = self.strip_bracket.sub("", s).strip()
        if len(t) < self.min_len:
            return None, "too_short"
        if len(t) > self.max_len:
            return None, "too_long"
        for reason, rx in self.drop.items():
            if rx.search(t):
                return None, reason
        if " " not in t and t.lower() in self.words:
            return None, "dictionary_word"
        return t, None


def chembl_names(f, inchikey: str) -> tuple[str | None, str | None, list[tuple[str, str]]]:
    """(chembl_id, pref_name, [(synonym, syn_type)]) for the parent and its salt forms."""
    try:
        mols = chembl.molecules_by_inchikey(f, inchikey)
    except HttpError:
        return None, None, []
    if not mols:
        return None, None, []
    m = mols[0]
    cid = m["molecule_chembl_id"]
    names = [(s["molecule_synonym"], s["syn_type"]) for s in m.get("molecule_synonyms") or []]
    try:  # trade names usually sit on salt forms, whose parent is this molecule
        status, data = f.get_json("molecule.json", {"molecule_hierarchy__parent_chembl_id": cid, "limit": 50})
        for child in (data or {}).get("molecules", []) if status == 200 else []:
            if child["molecule_chembl_id"] != cid:
                names += [(s["molecule_synonym"], s["syn_type"]) for s in child.get("molecule_synonyms") or []]
                if child.get("pref_name"):
                    names.append((child["pref_name"], "SALT_PREF_NAME"))
    except HttpError:
        pass
    return cid, m.get("pref_name"), names


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def run(conn: sqlite3.Connection) -> dict:
    rules = load_rules()
    filt = PubchemFilter(rules)
    fx = fixture.load()
    res = Resolver(fx)                                   # the resolver's own normalise()/strip()
    pc, ch = pubchem.fetcher(conn), chembl.fetcher(conn)
    ident = [r for r in csv.DictReader(open(SCALE / "identity.csv", encoding="utf-8")) if r["outcome"] == "resolved"]
    by_key = defaultdict(list)
    for r in ident:
        by_key[r["inchikey"]].append(r)

    compounds, rows = {}, []          # rows: one per (compound, candidate string)
    seed_keys = {c["key"] for c in fx["compounds"]}
    for ik, rs in sorted(by_key.items()):
        cid = int(rs[0]["parent_cid"])
        chembl_id, pref, ch_names = chembl_names(ch, ik)
        canonical = (pref or rs[0]["pubchem_title"] or rs[0]["drugage_name"]).strip()
        key = "s-" + _slug(canonical)
        while key in compounds or key in seed_keys:
            key += "-x"
        cand = defaultdict(set)       # string -> {source tags}
        query = set()
        for r in rs:
            cand[" ".join(r["drugage_name"].split())].add("drugage")
            query.add(" ".join(r["drugage_name"].split()))
        if pref:
            cand[pref].add("chembl:PREF_NAME")
            query.add(pref)
        for s, t in ch_names:
            if t in rules["match_chembl_syn_types"] or t == "SALT_PREF_NAME":
                cand[s].add(f"chembl:{t}")
                if t in rules["query_chembl_syn_types"]:
                    query.add(s)
        dropped, n_kept = [], 0
        for s in pubchem.synonyms(pc, cid):
            kept, why = filt(s)
            if kept and n_kept >= rules["pubchem_max_rank"]:
                kept, why = None, "beyond_max_rank"
            if kept:
                n_kept += 1
                cand[kept].add("pubchem")
            else:
                dropped.append((s, why))
        compounds[key] = {"key": key, "canonical_name": canonical.lower(), "inchikey": ik, "pubchem_cid": cid,
                          "chembl_id": chembl_id, "drugage_names": sorted({r["drugage_name"] for r in rs}),
                          "cand": cand, "query": query, "dropped": dropped}

    # Collisions under the resolver's normalisation: normalise() and strip() forms.
    forms = lambda s: {f for f in (res.normalise(s), res.strip(res.normalise(s))) if f}
    owner = defaultdict(set)
    for k, c in compounds.items():
        for s in c["cand"]:
            for fm in forms(s):
                owner[fm].add(k)
    seed_forms = set()
    for c in fx["compounds"]:
        # A seed SYNONYM or REVIEW string is ambiguous with a scaled compound's name. A seed
        # NEGATIVE is not: "everolimus" in rapamycin's must_not_match says everolimus is a
        # different compound, which is exactly what the scaled everolimus entry is (v2 fix).
        for s in [c["canonical_name"]] + list(c["must_match"]) + list(c.get("needs_review", [])):
            seed_forms |= forms(s)

    combo_rx = re.compile(rules["combination_product_pattern"], re.IGNORECASE)
    out = []
    for k, c in compounds.items():
        match, review = [], []
        for s, src in sorted(c["cand"].items()):
            fm = forms(s)
            if not fm:
                continue
            others = set().union(*(owner[f] for f in fm)) - {k}
            seed_hit = bool(fm & seed_forms)
            combo = bool(combo_rx.search(s))
            fate = ("review_combination_product" if combo else "review_collision_seed" if seed_hit
                    else "review_collision" if others else "match")
            (match if fate == "match" else review).append(s)
            rows.append({"compound_key": k, "inchikey": c["inchikey"], "synonym": s, "sources": "|".join(sorted(src)),
                         "fate": fate, "query": s in c["query"] and fate == "match",
                         "collides_with": "|".join(sorted(others)) + ("|SEED" if seed_hit else "")})
        for s, why in c["dropped"]:
            rows.append({"compound_key": k, "inchikey": c["inchikey"], "synonym": s, "sources": "pubchem",
                         "fate": f"dropped_{why}", "query": False, "collides_with": ""})
        out.append({"key": k, "role": "scaled", "canonical_name": c["canonical_name"], "inchikey": c["inchikey"],
                    "pubchem_cid": c["pubchem_cid"], "chembl_id": c["chembl_id"], "drugage_names": c["drugage_names"],
                    "must_match": match, "must_not_match": [], "needs_review": review, "route_excluded": [],
                    "query_terms": sorted(q for q in c["query"] if q in match)})

    with open(SCALE / "synonyms.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["compound_key", "inchikey", "synonym", "sources", "fate", "query", "collides_with"])
        w.writeheader()
        w.writerows(rows)
    with open(SCALE / "scaled_compounds.yaml", "w", encoding="utf-8") as fh:
        fh.write(f"# Generated by agesdk/scale_synonyms.py ({rules['version']}). Do not edit by hand.\n")
        yaml.safe_dump({"rules_version": rules["version"], "compounds": out}, fh, sort_keys=False, allow_unicode=True, width=110)

    fate = Counter(r["fate"] for r in rows)
    qterms = {q.lower() for c in out for q in c["query_terms"]}
    return {"compounds": len(out), "with_chembl": sum(1 for c in out if c["chembl_id"]),
            "strings_by_fate": dict(fate.most_common()),
            "match_terms": sum(len(c["must_match"]) for c in out),
            "query_terms_unique": len(qterms),
            "compounds_with_no_match_term": sum(1 for c in out if not c["must_match"])}
