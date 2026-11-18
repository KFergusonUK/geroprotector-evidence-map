"""PubMed (NCBI E-utilities), through the raw-layer cache. No API key: ≤3 requests/second."""
from __future__ import annotations

import json
import sqlite3
import xml.etree.ElementTree as ET

from agesdk.raw import CachedFetcher, HttpClient

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def fetcher(conn: sqlite3.Connection, client: HttpClient | None = None) -> CachedFetcher:
    return CachedFetcher(conn, "pubmed", BASE, client or HttpClient(min_interval_s=0.4), api_version="eutils")


def search(f: CachedFetcher, term: str, retmax: int = 200) -> list[str]:
    status, data = f.get_json("esearch.fcgi", {"db": "pubmed", "term": term, "retmax": retmax, "retmode": "json"})
    return data["esearchresult"]["idlist"] if status == 200 else []


def registry_ids(f: CachedFetcher, pmids: list[str]) -> dict[str, dict]:
    """{pmid: {title, nct_ids}} from each record's structured DataBank list (ClinicalTrials.gov)."""
    if not pmids:
        return {}
    resp = f.get("efetch.fcgi", {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"})
    if resp.http_status != 200:
        return {}
    out = {}
    for art in ET.fromstring(resp.body).iter("PubmedArticle"):
        pmid = art.findtext(".//MedlineCitation/PMID")
        ncts = [a.text for db in art.iter("DataBank") if db.findtext("DataBankName") == "ClinicalTrials.gov"
                for a in db.iter("AccessionNumber") if a.text]
        out[pmid] = {"title": "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else "",
                     "nct_ids": ncts}
    return out
