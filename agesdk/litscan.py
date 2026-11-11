"""Literature scan for pre-database lifespan signals (SPEC §11.4).

A curation queue, never an entry route. This module writes to
literature_candidate and fetch_log only; it never touches compound, crosswalk,
animal_evidence or any review table. A test enforces that.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

import yaml

from agesdk.db import PROJECT_ROOT
from agesdk.raw import CachedFetcher, HttpClient, last_watermark, log_fetch

RULES_PATH = PROJECT_ROOT / "data" / "rules" / "literature_scan.yaml"
SEARCH_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
ANNOT_BASE = "https://www.ebi.ac.uk/europepmc/annotations_api"
SOURCE = "europepmc-litscan"
ANNOT_BATCH = 8


def load_rules(path=RULES_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        rules = yaml.safe_load(fh)
    for k in ("version", "query", "stoplist", "default_window_days", "max_results"):
        if k not in rules:
            raise ValueError(f"literature_scan.yaml: missing {k}")
    if "{from}" not in rules["query"] or "{to}" not in rules["query"]:
        raise ValueError("literature_scan.yaml: query must contain {from} and {to}")
    return rules


def known_names(conn: sqlite3.Connection, drugage_rows: list[dict] | None = None) -> set[str]:
    """Names already in the map (compounds, synonyms) or in DrugAge (which will be)."""
    names = {r[0] for r in conn.execute("SELECT canonical_name FROM compound")}
    names |= {r[0] for r in conn.execute("SELECT synonym FROM compound_synonym")}
    names |= {r["compound_name"] for r in drugage_rows or []}
    return {n.strip().lower() for n in names if n}


def search(f: CachedFetcher, query: str, max_results: int) -> list[dict]:
    out, cursor = [], "*"
    while len(out) < max_results:
        status, data = f.get_json("search", {"query": query, "format": "json", "resultType": "lite",
                                             "pageSize": 100, "cursorMark": cursor})
        if status != 200:
            break
        hits = data.get("resultList", {}).get("result", [])
        out.extend(hits)
        nxt = data.get("nextCursorMark")
        if not hits or not nxt or nxt == cursor:
            break
        cursor = nxt
    return out[:max_results]


def chemicals(fa: CachedFetcher, pmids: list[str]) -> dict[str, list[str]]:
    """Text-mined chemical mentions per PMID (Europe PMC annotations, type Chemicals)."""
    found: dict[str, set[str]] = {p: set() for p in pmids}
    for i in range(0, len(pmids), ANNOT_BATCH):
        batch = pmids[i:i + ANNOT_BATCH]
        status, data = fa.get_json("annotationsByArticleIds",
                                   {"articleIds": ",".join(f"MED:{p}" for p in batch),
                                    "type": "Chemicals", "format": "JSON"})
        if status != 200:
            continue
        for art in data or []:
            pmid = str(art.get("extId", ""))
            for a in art.get("annotations", []):
                if pmid in found and a.get("exact"):
                    found[pmid].add(a["exact"].strip())
    return {p: sorted(v) for p, v in found.items()}


def scan(conn: sqlite3.Connection, *, run_id: int | None = None, today: date | None = None,
         drugage_rows: list[dict] | None = None, client: HttpClient | None = None,
         rules: dict | None = None) -> dict:
    rules = rules or load_rules()
    today = today or date.today()
    wm_params = {"query_version": rules["version"]}
    wm = last_watermark(conn, SOURCE, "search", wm_params)
    start = date.fromisoformat(wm) if wm else today - timedelta(days=rules["default_window_days"])
    query = rules["query"].replace("{from}", start.isoformat()).replace("{to}", today.isoformat())

    client = client or HttpClient(min_interval_s=0.3)
    fs = CachedFetcher(conn, "europepmc", SEARCH_BASE, client, api_version="rest-v6")
    fa = CachedFetcher(conn, "europepmc", ANNOT_BASE, client, api_version="annotations-api")
    try:
        hits = [h for h in search(fs, query, rules["max_results"]) if h.get("pmid")]
        mentions = chemicals(fa, [h["pmid"] for h in hits])
    except Exception as e:
        log_fetch(conn, source=SOURCE, endpoint="search", params=wm_params, outcome="error",
                  run_id=run_id, note=str(e))
        raise

    known = known_names(conn, drugage_rows)
    stop = {s.lower() for s in rules["stoplist"]}
    queued = skipped_known = 0
    for h in hits:
        # One entry per name, case-insensitively (annotations repeat 'Dopamine'/'dopamine').
        chems = {c.lower(): c for c in mentions.get(h["pmid"], []) if c.lower() not in stop}
        unmatched = sorted(v for k, v in chems.items() if k not in known)
        matched = sorted(v for k, v in chems.items() if k in known)
        if not unmatched:
            skipped_known += 1
            continue
        cur = conn.execute(
            """INSERT OR IGNORE INTO literature_candidate
               (pmid, title, journal, first_publication_date, query_version, run_id,
                unmatched_chemicals, matched_chemicals)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (h["pmid"], h.get("title", ""), h.get("journalTitle"), h.get("firstPublicationDate"),
             rules["version"], run_id, json.dumps(unmatched), json.dumps(matched)))
        queued += cur.rowcount
    conn.commit()
    log_fetch(conn, source=SOURCE, endpoint="search", params=wm_params,
              outcome="changed" if queued else "unchanged", run_id=run_id, watermark=today.isoformat(),
              api_version="rest-v6", note=json.dumps({"from": start.isoformat(), "to": today.isoformat(),
                                                      "hits": len(hits), "queued": queued,
                                                      "only_known_chemicals": skipped_known}))
    return {"query_version": rules["version"], "from": start.isoformat(), "to": today.isoformat(),
            "hits": len(hits), "queued": queued, "only_known_chemicals": skipped_known}
