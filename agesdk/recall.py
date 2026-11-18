"""Recall check for the registry fetch (before the resolver, SPEC §7 step 2→3).

Precision problems are visible inside the fetched data; a systematic miss is not.
This draws an independent sample of trials known from the literature — for each
compound, the most-cited randomised-trial papers in PubMed (ranked by OpenAlex citation
counts) whose record carries a ClinicalTrials.gov registration in its structured
DataBank list — verifies each trial in the registry, and asks whether the fetch caught it.

The sample does not come from our own query strings, so it can expose misses. Every
lookup goes through the raw layer (PubMed E-utilities; OpenAlex; ClinicalTrials.gov
single-study endpoint, which staging ignores). Europe PMC was the first choice but its
search returned HTTP 500 for every query on 2026-11-18.
"""
from __future__ import annotations

import json
import re
import sqlite3

import yaml

from agesdk import ctgov_report
from agesdk.db import PROJECT_ROOT
from agesdk.raw import CachedFetcher, HttpClient
from agesdk.sources import ctgov, openalex, pubmed

SAMPLE_PATH = PROJECT_ROOT / "data" / "fixtures" / "ctgov_recall_sample.yaml"
NCT_RE = re.compile(r"NCT\d{8}")
PER_COMPOUND = 2

# PubMed title queries: the names papers actually use (canonical names can be rare in titles).
TITLE_QUERY = {
    "rapamycin": "(sirolimus[ti] OR rapamycin[ti])",
    "17a-estradiol": '("17-alpha-estradiol"[ti] OR alfatradiol[ti] OR "17alpha-estradiol"[ti])',
    "ndga": "(nordihydroguaiaretic[ti] OR NDGA[ti] OR masoprocol[ti])",
    "akg": "(ketoglutarate[ti] OR ketoglutaric[ti])",
    "nmn": '"nicotinamide mononucleotide"[ti]',
    "nr": '"nicotinamide riboside"[ti]',
    "lithium": "lithium[ti]",
}
CANDIDATE_POOL = 200      # PubMed records per compound before citation ranking
TOP_FETCH = 12            # most-cited records whose registrations are read


def _query(key: str, canonical: str) -> str:
    title = TITLE_QUERY.get(key, f'"{canonical}"[ti]')
    return f"{title} AND randomized controlled trial[pt] AND clinicaltrials.gov[si]"


def candidates(f_pm: CachedFetcher, f_oa: CachedFetcher, key: str, canonical: str,
               n: int = PER_COMPOUND) -> list[dict]:
    pmids = pubmed.search(f_pm, _query(key, canonical), retmax=CANDIDATE_POOL)
    cites = openalex.citation_counts(f_oa, pmids)
    ranked = sorted(pmids, key=lambda p: -cites.get(p, 0))[:TOP_FETCH]
    recs = pubmed.registry_ids(f_pm, ranked)
    out, seen = [], set()
    for pm in ranked:
        ids = [i for i in recs.get(pm, {}).get("nct_ids", []) if NCT_RE.fullmatch(i) and i not in seen]
        if ids:
            seen.add(ids[0])
            out.append({"nct_id": ids[0], "pmid": pm, "title": recs[pm]["title"][:160], "cited_by": cites.get(pm, 0)})
        if len(out) >= n:
            break
    return out


def registry_record(f_ct: ctgov.Fetcher, nct: str) -> dict | None:
    resp = f_ct.get(f"studies/{nct}", {"fields": "protocolSection", "format": "json"})
    return json.loads(resp.body) if resp.http_status == 200 else None


def classify(record: dict, pattern: re.Pattern) -> str:
    """Where the registry record names the compound: 'intervention_name', 'intervention_other'
    (other names / description / arm labels), 'arms_or_title' (arm descriptions, titles,
    summary), or 'absent' (the paper's trial does not name the compound at all)."""
    ps = record.get("protocolSection", {})
    ivs = ps.get("armsInterventionsModule", {}).get("interventions", [])
    low = lambda x: ctgov_report._text(x)
    if any(pattern.search(low(iv.get("name"))) for iv in ivs):
        return "intervention_name"
    if any(pattern.search(low(" | ".join(iv.get("otherNames", []) + iv.get("armGroupLabels", []))))
           or pattern.search(low(iv.get("description"))) for iv in ivs):
        return "intervention_other"
    arms = " ".join(a.get("label", "") + " " + a.get("description", "")
                    for a in ps.get("armsInterventionsModule", {}).get("armGroups", []))
    ident = ps.get("identificationModule", {})
    text = " ".join([arms, ident.get("briefTitle", ""), ident.get("officialTitle", ""),
                     ps.get("descriptionModule", {}).get("briefSummary", "")])
    return "arms_or_title" if pattern.search(low(text)) else "absent"


def run(conn: sqlite3.Connection, fx: dict, client: HttpClient | None = None, progress=None) -> dict:
    client = client or HttpClient(min_interval_s=ctgov.MIN_INTERVAL_S)
    f_pm, f_oa = pubmed.fetcher(conn, client), openalex.fetcher(conn, client)
    f_ct = ctgov.Fetcher(conn, client)
    plan = {}
    for t, k in conn.execute("SELECT query_term, compound_key FROM ctgov_query_plan WHERE term_source <> 'trap_decoy'"):
        plan.setdefault(k, []).append(t)
    excluded = [e["term"] for e in ctgov.load_rules().get("excluded_terms", [])]
    hits_by = {}
    for t, n in conn.execute("SELECT query_term, nct_id FROM ctgov_query_hit"):
        hits_by.setdefault(n, set()).add(t)
    sample = []
    for c in fx["compounds"]:
        if c["role"] not in ("seed", "class_test_case") or c["key"] not in plan:
            continue
        pattern = ctgov_report._pattern(plan[c["key"]] + excluded if c["key"] in ("aspirin", "nr") else plan[c["key"]])
        if progress:
            progress(f"{c['key']}: searching PubMed")
        for cand in candidates(f_pm, f_oa, c["key"], c["canonical_name"]):
            if progress:
                progress(f"  {cand['nct_id']} (PMID {cand['pmid']})")
            rec = registry_record(f_ct, cand["nct_id"])
            where = classify(rec, pattern) if rec else "not_in_registry"
            found_by = sorted(t for t in hits_by.get(cand["nct_id"], set()) if t in plan[c["key"]])
            sample.append({"compound": c["key"], **cand, "registry": where,
                           "eligible": where in ("intervention_name", "intervention_other", "arms_or_title"),
                           "caught": bool(found_by), "caught_by": found_by,
                           "other_compounds_hit": sorted({k for k, ts in plan.items()
                                                          for t in hits_by.get(cand["nct_id"], set()) if t in ts}
                                                         - {c["key"]})})
    eligible = [s for s in sample if s["eligible"]]
    summary = {"sampled": len(sample), "eligible": len(eligible),
               "caught": sum(s["caught"] for s in eligible),
               "missed": [s["nct_id"] for s in eligible if not s["caught"]],
               "by_registry_field": {k: sum(1 for s in eligible if s["registry"] == k)
                                     for k in ("intervention_name", "intervention_other", "arms_or_title")}}
    return {"summary": summary, "sample": sample}


def save(result: dict, path=SAMPLE_PATH) -> None:
    header = ("# Recall sample for the ClinicalTrials.gov fetch (generated by agesdk.recall; do not hand-edit).\n"
              "# Per compound: the most-cited PubMed randomised-trial papers (OpenAlex citation counts) with a\n"
              "# ClinicalTrials.gov registration in the record, verified in the registry.\n"
              "# 'eligible' = the registry record names the compound.\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header)
        yaml.safe_dump(result, fh, sort_keys=False, allow_unicode=True, width=110)
