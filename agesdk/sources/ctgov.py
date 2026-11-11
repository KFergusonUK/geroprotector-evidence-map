"""ClinicalTrials.gov API v2 → raw layer, incrementally (SPEC §11.1).

Per search term, the high-water mark is the registry's data date at the last
successful fetch, kept in fetch_log. The next refresh asks only for studies whose
LastUpdatePostDate is on or after (watermark − overlap). A term never fetched
before gets its full history.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

from agesdk.raw import CachedFetcher, HttpClient, last_watermark, log_fetch

SOURCE = "ctgov"
BASE = "https://clinicaltrials.gov/api/v2"
PAGE_SIZE = 100
OVERLAP_DAYS = 1      # re-ask for the boundary day; identical pages are not re-stored


def version(client: HttpClient) -> dict:
    status, body, _ = client.get(f"{BASE}/version")
    return json.loads(body) if status == 200 else {}


def fetcher(conn: sqlite3.Connection, client: HttpClient, api_version: str | None) -> CachedFetcher:
    return CachedFetcher(conn, SOURCE, BASE, client, api_version=api_version)


def watermark_params(term: str) -> dict:
    """fetch_log key for a term (independent of the date window)."""
    return {"query.intr": term}


def search_params(term: str, since: str | None) -> dict:
    p = {"query.intr": term, "pageSize": PAGE_SIZE, "countTotal": "true", "format": "json"}
    if since:
        p["filter.advanced"] = f"AREA[LastUpdatePostDate]RANGE[{since},MAX]"
    return p


def refresh_term(conn: sqlite3.Connection, f: CachedFetcher, term: str, *, data_date: str,
                 run_id: int | None = None, max_pages: int = 200) -> dict:
    """Fetch studies for one intervention term updated since its watermark."""
    wm = last_watermark(conn, SOURCE, "studies", watermark_params(term))
    since = (date.fromisoformat(wm) - timedelta(days=OVERLAP_DAYS)).isoformat() if wm else None
    params = search_params(term, since)
    raw_ids, n_studies, token, pages = [], 0, None, 0
    try:
        while True:
            page_params = dict(params, **({"pageToken": token} if token else {}))
            resp = f.get("studies", page_params)
            data = json.loads(resp.body)
            raw_ids.append(resp.id)
            n_studies += len(data.get("studies", []))
            token = data.get("nextPageToken")
            pages += 1
            if not token or pages >= max_pages:
                break
    except Exception as e:  # record the failure; the watermark does not advance
        log_fetch(conn, source=SOURCE, endpoint="studies", params=watermark_params(term), outcome="error",
                  run_id=run_id, note=f"since={since}: {e}")
        raise
    log_fetch(conn, source=SOURCE, endpoint="studies", params=watermark_params(term),
              outcome="changed" if n_studies else "unchanged", run_id=run_id,
              raw_response_id=raw_ids[-1] if raw_ids else None, watermark=data_date,
              api_version=f.api_version,
              note=json.dumps({"since": since, "studies": n_studies, "pages": pages,
                               "raw_response_ids": raw_ids, "truncated": bool(token)}))
    return {"term": term, "since": since, "studies": n_studies, "pages": pages}


def refresh(conn: sqlite3.Connection, terms: list[str], *, run_id: int | None = None,
            client: HttpClient | None = None) -> dict:
    client = client or HttpClient(min_interval_s=1.2)   # stay well under the API's rate limit
    v = version(client)
    data_date = (v.get("dataTimestamp") or date.today().isoformat())[:10]
    f = fetcher(conn, client, f"{v.get('apiVersion', '?')} data {v.get('dataTimestamp', '?')}")
    results = [refresh_term(conn, f, t, data_date=data_date, run_id=run_id) for t in terms]
    return {"api_version": v.get("apiVersion"), "data_timestamp": v.get("dataTimestamp"),
            "terms": len(terms), "studies": sum(r["studies"] for r in results)}
