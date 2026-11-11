"""ClinicalTrials.gov API v2 → raw layer (SPEC §7 step 2, §11.1).

Two phases, both stored verbatim in raw_response with the request parameters and the
API version:

1. **Hits.** Per query string, the NCT IDs (and last-update dates) of matching studies,
   searched in the intervention field (``query.intr``). One query per synonym, so every
   hit records the string that produced it — evidence for the resolver's precision
   check (step 4). ClinicalTrials.gov applies its own synonym expansion, so many
   synonyms return overlapping sets.
2. **Full records.** Each study once, batched by NCT ID (``filter.ids``), with
   ``protocolSection``, ``derivedSection`` (MeSH browse modules) and ``hasResults``. The
   posted-results section is not requested: it is large and not needed until results
   reporting is assessed from status and dates (step 5).

The raw layer is the cache: a re-run makes no network calls for anything stored. The
staging tables (ctgov_*) are rebuilt from the raw layer by :func:`stage`.

Incremental refresh (§11.1): per query string, hits are requested only for studies
whose LastUpdatePostDate is on or after the term's high-water mark (minus overlap);
those studies' full records are then re-fetched, bypassing the cache.
"""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from datetime import date, timedelta

from agesdk.raw import CachedFetcher, HttpClient, StoredResponse, last_watermark, log_fetch

SOURCE = "ctgov"
BASE = "https://clinicaltrials.gov/api/v2"
HIT_FIELDS = "NCTId,LastUpdatePostDate"
FULL_FIELDS = "protocolSection,derivedSection,hasResults"
HIT_PAGE_SIZE = 1000
ID_BATCH = 100
OVERLAP_DAYS = 1
MIN_INTERVAL_S = 1.2          # well under the API's published rate limit


def version(client: HttpClient) -> dict:
    status, body, _ = client.get(f"{BASE}/version")
    return json.loads(body) if status == 200 else {}


def version_string(v: dict) -> str:
    return f"{v.get('apiVersion', '?')} data {v.get('dataTimestamp', '?')}"


class Fetcher(CachedFetcher):
    """Cache-first fetcher that looks up the API version only when it must hit the network,
    and counts network calls (zero on an idempotent re-run)."""

    def __init__(self, conn, client: HttpClient):
        super().__init__(conn, SOURCE, BASE, client, api_version=None)
        self.version: dict | None = None
        self.network_calls = 0

    def ensure_version(self) -> dict:
        if self.version is None:
            self.version = version(self.client)
            self.api_version = version_string(self.version)
            self.network_calls += 1
        return self.version

    def get(self, endpoint, params=None, *, refresh=False) -> StoredResponse:
        if not refresh:
            row = self.store.latest(self.source, endpoint.lstrip("/"), params)
            if row is not None:
                return StoredResponse(row["id"], False, row["response_body"], row["http_status"],
                                      row["fetched_at"], row["api_version"])
        self.ensure_version()
        self.network_calls += 1
        return super().get(endpoint, params, refresh=True)

    def data_date(self) -> str:
        return (self.ensure_version().get("dataTimestamp") or date.today().isoformat())[:10]


# ---------------------------------------------------------------- query plan

DOSE_RE = re.compile(r"\d+(\.\d+)?\s*(mg|g|mcg|µg|ug|ppm|ml|%)(\b|/)", re.IGNORECASE)
DASHES = dict.fromkeys(map(ord, "‐‑‒–—−"), "-")


def normalise_term(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", s).translate(DASHES).split())


def seed_query_plan(fx: dict, roles=("seed", "class_test_case")) -> list[dict]:
    """Query strings for the seed compounds: canonical name plus the fixture's must_match
    synonyms. Strings carrying a dose ("aspirin 81 mg") are resolver test inputs, not names,
    and are skipped. Case and dash variants collapse to one query."""
    plan, seen = [], {}
    for c in fx["compounds"]:
        if c["role"] not in roles:
            continue
        candidates = [(c["canonical_name"], "canonical_name")] + [(m, "must_match") for m in c["must_match"]]
        for raw, source in candidates:
            term = normalise_term(str(raw))
            if not term or DOSE_RE.search(term):
                continue
            k = term.lower()
            if k in seen:
                if seen[k] != c["key"]:
                    raise ValueError(f"query term {term!r} claimed by {seen[k]} and {c['key']}")
                continue
            seen[k] = c["key"]
            plan.append({"query_term": term, "compound_key": c["key"], "term_source": source})
    return plan


def save_plan(conn: sqlite3.Connection, plan: list[dict], plan_version: str) -> None:
    conn.executemany("INSERT OR REPLACE INTO ctgov_query_plan (query_term, compound_key, term_source, plan_version) "
                     "VALUES (:query_term, :compound_key, :term_source, :pv)",
                     [dict(p, pv=plan_version) for p in plan])
    conn.commit()


# ---------------------------------------------------------------- fetching

def hit_params(term: str, since: str | None = None) -> dict:
    p = {"query.intr": term, "fields": HIT_FIELDS, "pageSize": HIT_PAGE_SIZE,
         "countTotal": "true", "format": "json"}
    if since:
        p["filter.advanced"] = f"AREA[LastUpdatePostDate]RANGE[{since},MAX]"
    return p


def search_hits(f: Fetcher, term: str, since: str | None = None, *, max_pages: int = 100) -> dict:
    """All NCT IDs matching ``term`` (optionally updated since a date). Cached page by page."""
    params, token, ids, raw_ids, total = hit_params(term, since), None, {}, [], None
    for _ in range(max_pages):
        resp = f.get("studies", dict(params, **({"pageToken": token} if token else {})))
        data = json.loads(resp.body)
        raw_ids.append(resp.id)
        total = data.get("totalCount", total)
        for s in data.get("studies", []):
            ps = s.get("protocolSection", {})
            nct = ps.get("identificationModule", {}).get("nctId")
            if nct:
                ids[nct] = ps.get("statusModule", {}).get("lastUpdatePostDateStruct", {}).get("date")
        token = data.get("nextPageToken")
        if not token:
            break
    return {"term": term, "since": since, "ids": ids, "raw_ids": raw_ids, "total": total,
            "truncated": bool(token)}


def full_params(batch: list[str]) -> dict:
    return {"filter.ids": ",".join(batch), "fields": FULL_FIELDS, "pageSize": len(batch), "format": "json"}


def fetch_full(f: Fetcher, nct_ids, *, refresh: bool = False) -> dict:
    """Full records for the given studies, in batches. ``refresh`` bypasses the cache
    (for studies known to have changed)."""
    ids = sorted(set(nct_ids))
    raw_ids, returned = [], set()
    for i in range(0, len(ids), ID_BATCH):
        batch = ids[i:i + ID_BATCH]
        resp = f.get("studies", full_params(batch), refresh=refresh)
        raw_ids.append(resp.id)
        returned |= {s["protocolSection"]["identificationModule"]["nctId"]
                     for s in json.loads(resp.body).get("studies", [])}
    return {"requested": len(ids), "returned": len(returned & set(ids)),
            "missing": sorted(set(ids) - returned), "raw_ids": raw_ids}


# ---------------------------------------------------------------- staging

def _date(struct):
    return (struct or {}).get("date")


def stage(conn: sqlite3.Connection) -> dict:
    """Rebuild ctgov_query_hit, ctgov_study and ctgov_intervention from the raw layer.
    Raw responses are applied in id order, so a later record of a study supersedes an
    earlier one."""
    conn.execute("DELETE FROM ctgov_intervention")
    conn.execute("DELETE FROM ctgov_study")
    conn.execute("DELETE FROM ctgov_query_hit")
    n_hits = n_studies = 0
    reader = conn.cursor()   # stream: the raw layer can be large
    for row in reader.execute("SELECT id, request_params, response_body FROM raw_response "
                              "WHERE source = ? AND endpoint = 'studies' AND http_status = 200 ORDER BY id",
                              (SOURCE,)):
        params = json.loads(row["request_params"])
        data = json.loads(row["response_body"])
        if "query.intr" in params:
            for s in data.get("studies", []):
                ps = s.get("protocolSection", {})
                conn.execute("INSERT OR REPLACE INTO ctgov_query_hit (query_term, nct_id, last_update_post_date, "
                             "raw_response_id) VALUES (?, ?, ?, ?)",
                             (params["query.intr"], ps["identificationModule"]["nctId"],
                              _date(ps.get("statusModule", {}).get("lastUpdatePostDateStruct")), row["id"]))
                n_hits += 1
        elif "filter.ids" in params:
            for s in data.get("studies", []):
                _stage_study(conn, row["id"], s)
                n_studies += 1
    conn.commit()
    return {"hit_rows": n_hits, "study_records": n_studies,
            "studies": conn.execute("SELECT count(*) FROM ctgov_study").fetchone()[0],
            "interventions": conn.execute("SELECT count(*) FROM ctgov_intervention").fetchone()[0]}


def _stage_study(conn: sqlite3.Connection, raw_id: int, s: dict) -> None:
    ps = s.get("protocolSection", {})
    ds = s.get("derivedSection", {})
    ident, status = ps.get("identificationModule", {}), ps.get("statusModule", {})
    design, sponsor = ps.get("designModule", {}), ps.get("sponsorCollaboratorsModule", {})
    arms = ps.get("armsInterventionsModule", {})
    nct = ident["nctId"]
    dumps = lambda x: None if x is None else json.dumps(x, ensure_ascii=False)
    conn.execute("DELETE FROM ctgov_intervention WHERE nct_id = ?", (nct,))
    conn.execute(
        """INSERT OR REPLACE INTO ctgov_study (
             nct_id, raw_response_id, last_update_post_date, brief_title, overall_status, study_type, phases,
             enrollment, start_date, primary_completion_date, completion_date, results_first_post_date,
             has_results, lead_sponsor, lead_sponsor_class, interventions, arm_groups, conditions_module,
             condition_browse, intervention_browse, outcomes_module, study_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (nct, raw_id, _date(status.get("lastUpdatePostDateStruct")), ident.get("briefTitle"),
         status.get("overallStatus"), design.get("studyType"), dumps(design.get("phases")),
         (design.get("enrollmentInfo") or {}).get("count"), _date(status.get("startDateStruct")),
         _date(status.get("primaryCompletionDateStruct")), _date(status.get("completionDateStruct")),
         _date(status.get("resultsFirstPostDateStruct")), int(bool(s.get("hasResults"))),
         (sponsor.get("leadSponsor") or {}).get("name"), (sponsor.get("leadSponsor") or {}).get("class"),
         dumps(arms.get("interventions", [])), dumps(arms.get("armGroups")), dumps(ps.get("conditionsModule")),
         dumps(ds.get("conditionBrowseModule")), dumps(ds.get("interventionBrowseModule")),
         dumps(ps.get("outcomesModule")), dumps(s)))
    for i, iv in enumerate(arms.get("interventions", [])):
        conn.execute(
            """INSERT INTO ctgov_intervention (nct_id, idx, intervention_type, name, description, other_names,
                                               arm_group_labels, object_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (nct, i, iv.get("type"), iv.get("name"), iv.get("description"), dumps(iv.get("otherNames")),
             dumps(iv.get("armGroupLabels")), dumps(iv)))


# ---------------------------------------------------------------- orchestration

def fetch_seed(conn: sqlite3.Connection, fx: dict, *, client: HttpClient | None = None,
               run_id: int | None = None) -> dict:
    """§7 step 2: hits for every seed query string, then full records for every study not
    already stored. Idempotent: a re-run with everything cached makes no network calls."""
    plan = seed_query_plan(fx)
    save_plan(conn, plan, f"fixture-{fx.get('fixture_version')}")
    f = Fetcher(conn, client or HttpClient(min_interval_s=MIN_INTERVAL_S))
    per_term = []
    for p in plan:
        before = f.network_calls
        res = search_hits(f, p["query_term"])
        per_term.append({**p, "hits": len(res["ids"]), "total": res["total"], "truncated": res["truncated"]})
        if f.network_calls > before:   # log real fetches; record the term's high-water mark
            log_fetch(conn, source=SOURCE, endpoint="studies", params=watermark_params(p["query_term"]),
                      outcome="changed" if res["ids"] else "unchanged", run_id=run_id,
                      raw_response_id=res["raw_ids"][-1], watermark=f.data_date(), api_version=f.api_version,
                      note=json.dumps({"phase": "hits", "hits": len(res["ids"]), "total": res["total"],
                                       "truncated": res["truncated"]}))
    stage(conn)
    wanted = {r[0] for r in conn.execute("SELECT DISTINCT nct_id FROM ctgov_query_hit")}
    have = {r[0] for r in conn.execute("SELECT nct_id FROM ctgov_study")}
    missing = wanted - have
    full = fetch_full(f, missing) if missing else {"requested": 0, "returned": 0, "missing": [], "raw_ids": []}
    if full["requested"]:
        log_fetch(conn, source=SOURCE, endpoint="studies", params={"phase": "full_records"},
                  outcome="changed", run_id=run_id, raw_response_id=full["raw_ids"][-1],
                  api_version=f.api_version,
                  note=json.dumps({"requested": full["requested"], "returned": full["returned"],
                                   "missing": full["missing"][:50]}))
    staged = stage(conn)
    return {"terms": len(plan), "unique_studies": len(wanted), "fetched_full": full["requested"],
            "not_returned": full["missing"], "network_calls": f.network_calls,
            "api_version": f.api_version, "per_term": per_term, **staged}


def watermark_params(term: str) -> dict:
    """fetch_log key for a term's high-water mark (independent of the date window)."""
    return {"query.intr": term}


def refresh_term(conn: sqlite3.Connection, f: Fetcher, term: str, *, run_id: int | None = None) -> dict:
    """Incremental: hits updated since the term's watermark, then their full records afresh."""
    wm = last_watermark(conn, SOURCE, "studies", watermark_params(term))
    since = (date.fromisoformat(wm) - timedelta(days=OVERLAP_DAYS)).isoformat() if wm else None
    try:
        res = search_hits(f, term, since)
        full = fetch_full(f, res["ids"], refresh=bool(since)) if res["ids"] else {"requested": 0, "raw_ids": []}
    except Exception as e:  # the watermark does not advance on failure
        log_fetch(conn, source=SOURCE, endpoint="studies", params=watermark_params(term), outcome="error",
                  run_id=run_id, note=f"since={since}: {e}")
        raise
    log_fetch(conn, source=SOURCE, endpoint="studies", params=watermark_params(term),
              outcome="changed" if res["ids"] else "unchanged", run_id=run_id,
              raw_response_id=(full["raw_ids"] or res["raw_ids"])[-1], watermark=f.data_date(),
              api_version=f.api_version,
              note=json.dumps({"since": since, "studies": len(res["ids"]), "truncated": res["truncated"]}))
    return {"term": term, "since": since, "studies": len(res["ids"])}


def refresh(conn: sqlite3.Connection, terms: list[str] | None = None, *, run_id: int | None = None,
            client: HttpClient | None = None) -> dict:
    """§11 incremental refresh. Terms default to the stored query plan."""
    if terms is None:
        terms = [r[0] for r in conn.execute("SELECT query_term FROM ctgov_query_plan ORDER BY query_term")]
    f = Fetcher(conn, client or HttpClient(min_interval_s=MIN_INTERVAL_S))
    v = f.ensure_version()
    results = [refresh_term(conn, f, t, run_id=run_id) for t in terms]
    if any(r["studies"] for r in results):
        stage(conn)
    return {"api_version": v.get("apiVersion"), "data_timestamp": v.get("dataTimestamp"),
            "terms": len(terms), "studies": sum(r["studies"] for r in results)}
