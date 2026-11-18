"""OpenAlex, through the raw-layer cache. No key needed (SPEC §3)."""
from __future__ import annotations

import sqlite3

from agesdk.raw import CachedFetcher, HttpClient

BASE = "https://api.openalex.org"
BATCH = 50


def fetcher(conn: sqlite3.Connection, client: HttpClient | None = None) -> CachedFetcher:
    return CachedFetcher(conn, "openalex", BASE, client or HttpClient(min_interval_s=0.2), api_version="works")


def citation_counts(f: CachedFetcher, pmids: list[str]) -> dict[str, int]:
    out = {}
    for i in range(0, len(pmids), BATCH):
        batch = pmids[i:i + BATCH]
        status, data = f.get_json("works", {"filter": "pmid:" + "|".join(batch), "per-page": BATCH,
                                            "select": "ids,cited_by_count"})
        for w in (data or {}).get("results", []) if status == 200 else []:
            pm = (w.get("ids") or {}).get("pmid", "").rsplit("/", 1)[-1]
            if pm:
                out[pm] = w.get("cited_by_count") or 0
    return out
