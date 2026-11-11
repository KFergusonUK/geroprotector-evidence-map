"""Europe PMC REST, through the raw-layer cache. Publication metadata and authors (SPEC §5.4)."""
from __future__ import annotations

import sqlite3

from agesdk.raw import CachedFetcher, HttpClient

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"


def fetcher(conn: sqlite3.Connection, client: HttpClient | None = None) -> CachedFetcher:
    return CachedFetcher(conn, "europepmc", BASE, client or HttpClient(min_interval_s=0.2),
                         api_version="rest-v6")


def article_by_pmid(f: CachedFetcher, pmid: str) -> dict | None:
    """Core record (title, abstract, full author list with affiliations) for one PMID."""
    status, data = f.get_json("search", {"query": f"EXT_ID:{pmid} AND SRC:MED",
                                         "resultType": "core", "format": "json"})
    if status != 200:
        return None
    hits = data.get("resultList", {}).get("result", [])
    return hits[0] if hits else None


def authors(article: dict) -> list[dict]:
    """[{full_name, orcid, affiliation}] in author order."""
    out = []
    for a in (article.get("authorList") or {}).get("author", []):
        affs = ((a.get("authorAffiliationDetailsList") or {}).get("authorAffiliation") or [])
        orcid = None
        for aid in ((a.get("authorId") or {}) and [a["authorId"]] or []):
            if aid.get("type") == "ORCID":
                orcid = aid.get("value")
        out.append({"full_name": a.get("fullName") or a.get("collectiveName") or "",
                    "orcid": orcid,
                    "affiliation": affs[0].get("affiliation") if affs else None})
    return out
