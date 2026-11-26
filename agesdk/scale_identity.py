"""Stage 1 of the scaled synonym pipeline (docs/synonym_pipeline.md): DrugAge name -> identity.

Mechanical, cache-first: every PubChem lookup lands in raw_response, so a re-run makes no
network calls. Writes nothing to the resolver's inputs; the report is the output.

Outcomes per DrugAge name:
  seed       already a seed fixture entry (the hand fixture applies)
  resolved   exactly one parent CID, single component, full InChIKey
  ambiguous  the name maps to several parent CIDs
  not_found  PubChem knows no such name
  mixture    the parent is multi-component, or PubChem gives no parent
  rejected   a named person rejected the mechanical resolution
  needs_check resolved only after dropping a trailing bracketed description: no automatic
             synonyms until a named person signs it off (data/scale/identity_decisions.yaml)
"""
from __future__ import annotations

import csv
import re
import sqlite3
from collections import Counter
from pathlib import Path

import yaml

from agesdk import fixture
from agesdk.raw import HttpError
from agesdk.sources import drugage, pubchem

OUT = Path(__file__).resolve().parent.parent / "data" / "scale" / "identity.csv"
FIELDS = ["drugage_name", "outcome", "n_cids", "parent_cid", "inchikey", "formula", "pubchem_title", "detail"]


def clean_name(name: str) -> str:
    """Mechanical clean-up only (no judgement): collapse whitespace; drop a trailing bracketed
    description, e.g. "SRT1720 (SIRT1 activator)" -> "SRT1720". Typos are NOT corrected here."""
    n = " ".join(name.split())
    m = re.search(r"\s*\(([^()]*)\)\s*$", n)
    # A bracket that lists components ("PB125 (carnosol, withaferin A and luteolin)") says the
    # thing is a mixture: keep it, so the name stays unresolved rather than resolving the code.
    if m and not re.search(r",|\band\b|mixture|\+", m.group(1), re.IGNORECASE):
        n = n[: m.start()] or n
    return n


def _lookup(f, name: str) -> list[int]:
    try:
        return [c for c in pubchem.cids_for_name(f, name) if c]
    except HttpError:
        return []


def resolve_name(f, name: str) -> dict:
    row = {"drugage_name": name, "n_cids": 0, "parent_cid": "", "inchikey": "", "formula": "",
           "pubchem_title": "", "detail": ""}
    cids = _lookup(f, name.strip())
    if not cids:
        cleaned = clean_name(name)
        if cleaned != name.strip():
            cids = _lookup(f, cleaned)
            if cids:
                row["detail"] = f"looked up as {cleaned!r}; "
    if not cids:
        return {**row, "outcome": "not_found"}
    bracket_dropped = bool(row["detail"]) and " ".join(name.split()) != clean_name(name)
    parents = set()
    for cid in cids:
        p = pubchem.parent_cids(f, cid)
        parents.update(p if p else [None])
    row["n_cids"] = len(cids)
    if None in parents:
        return {**row, "outcome": "mixture", "detail": row["detail"] + "no PubChem parent for a CID"}
    if len(parents) > 1:
        return {**row, "outcome": "ambiguous", "detail": row["detail"] + f"parents {sorted(parents)[:8]}"}
    parent = parents.pop()
    props = pubchem.properties(f, parent) or {}
    row.update(parent_cid=parent, inchikey=props.get("InChIKey", ""), formula=props.get("MolecularFormula", ""),
               pubchem_title=props.get("Title", ""))
    if "." in row["formula"]:
        return {**row, "outcome": "mixture", "detail": row["detail"] + "parent is multi-component"}
    if len(row["inchikey"]) != 27:
        return {**row, "outcome": "mixture", "detail": row["detail"] + "no full InChIKey"}
    if bracket_dropped:
        # A bare code can resolve to an unrelated record (found 2026-11-26: "78c (CD38 inhibitor)"
        # -> a cyclopentyl azetidine carboxylate, not the CD38 inhibitor). Human sign-off first.
        return {**row, "outcome": "needs_check", "detail": row["detail"] + "resolved only after dropping a bracket"}
    return {**row, "outcome": "resolved"}


DECISIONS = OUT.parent / "identity_decisions.yaml"


def load_decisions() -> dict[str, dict]:
    """Named-person decisions only (decided_by set), keyed by DrugAge name."""
    if not DECISIONS.exists():
        return {}
    d = yaml.safe_load(open(DECISIONS, encoding="utf-8")) or {}
    out = {}
    def walk(x):
        if isinstance(x, dict):
            if "drugage_name" in x and x.get("decided_by"):
                out[x["drugage_name"]] = x
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(d)
    return out


def apply_decision(f, row: dict, dec: dict) -> dict:
    """A recorded decision overrides the mechanical outcome. Accepted targets are re-checked
    against the InChIKey recorded at decision time, so PubChem drift cannot swap a molecule."""
    tag = f"decision {dec['decision']} by {dec['decided_by']} {dec.get('decided_at', '')}"
    if dec["decision"] == "reject":
        return {**row, "outcome": "rejected", "detail": tag}
    if dec["decision"] in ("leave_mixture", "leave_unresolved"):
        return {**row, "detail": (row["detail"] + "; " if row["detail"] else "") + tag}
    props = pubchem.properties(f, int(dec["target_cid"])) or {}
    if props.get("InChIKey") != dec["target_inchikey"]:
        raise ValueError(f"{row['drugage_name']}: CID {dec['target_cid']} now has InChIKey {props.get('InChIKey')}, "
                         f"decision recorded {dec['target_inchikey']}")
    return {**row, "outcome": "resolved", "parent_cid": dec["target_cid"], "inchikey": dec["target_inchikey"],
            "formula": props.get("MolecularFormula", ""), "pubchem_title": props.get("Title", ""),
            "detail": f"{tag}: {dec['decision']} -> {dec.get('target', '')}"}


def run(conn: sqlite3.Connection, limit: int | None = None) -> dict:
    seed_names = {n for c in fixture.load()["compounds"] for n in c.get("drugage_names", [])}
    names = sorted({r["compound_name"] for r in drugage.current_rows(conn)})
    f = pubchem.fetcher(conn)
    decisions = load_decisions()
    rows = []
    for name in names[:limit] if limit else names:
        if name in seed_names:
            rows.append({**dict.fromkeys(FIELDS, ""), "drugage_name": name, "outcome": "seed"})
            continue
        row = resolve_name(f, name)
        rows.append(apply_decision(f, row, decisions[name]) if name in decisions else row)
    missing = set(decisions) - set(names)
    if missing:
        raise ValueError(f"decisions for names not in DrugAge: {sorted(missing)}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    resolved = [r for r in rows if r["outcome"] == "resolved"]
    dup = Counter(r["inchikey"] for r in resolved)
    return {"names": len(rows), "outcomes": dict(Counter(r["outcome"] for r in rows)),
            "resolved_inchikeys": len(dup),
            "inchikey_shared_by_several_names": {k: n for k, n in dup.items() if n > 1},
            "output": str(OUT)}
