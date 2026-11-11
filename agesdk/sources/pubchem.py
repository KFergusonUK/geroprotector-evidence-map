"""PubChem PUG REST, through the raw-layer cache. Policy: ≤5 requests/second."""
from __future__ import annotations

import sqlite3
import urllib.parse

from agesdk.raw import CachedFetcher, HttpClient

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PROPS = "Title,InChIKey,MolecularFormula,IUPACName"


def fetcher(conn: sqlite3.Connection, client: HttpClient | None = None) -> CachedFetcher:
    return CachedFetcher(conn, "pubchem", BASE, client or HttpClient(min_interval_s=0.25),
                         api_version="PUG-REST")


def cids_for_name(f: CachedFetcher, name: str) -> list[int]:
    status, data = f.get_json(f"compound/name/{urllib.parse.quote(name, safe='')}/cids/JSON")
    return data["IdentifierList"]["CID"] if status == 200 else []


def properties(f: CachedFetcher, cid: int) -> dict | None:
    status, data = f.get_json(f"compound/cid/{cid}/property/{PROPS}/JSON")
    return data["PropertyTable"]["Properties"][0] if status == 200 else None


def parent_cids(f: CachedFetcher, cid: int) -> list[int]:
    """PubChem's parent compound (salt/hydrate stripped)."""
    status, data = f.get_json(f"compound/cid/{cid}/cids/JSON", {"cids_type": "parent"})
    return data["IdentifierList"]["CID"] if status == 200 else []


def synonyms(f: CachedFetcher, cid: int) -> list[str]:
    status, data = f.get_json(f"compound/cid/{cid}/synonyms/JSON")
    if status != 200:
        return []
    return data["InformationList"]["Information"][0].get("Synonym", [])
