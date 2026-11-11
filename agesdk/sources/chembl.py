"""ChEMBL REST, through the raw-layer cache. Source of ATC codes (SPEC §5.5)."""
from __future__ import annotations

import sqlite3

from agesdk.raw import CachedFetcher, HttpClient

BASE = "https://www.ebi.ac.uk/chembl/api/data"


def chembl_version(client: HttpClient) -> str | None:
    """ChEMBL release, e.g. 'ChEMBL_35', recorded as api_version on every row."""
    import json
    status, body, _ = client.get(f"{BASE}/status.json")
    return json.loads(body).get("chembl_db_version") if status == 200 else None


def fetcher(conn: sqlite3.Connection, client: HttpClient | None = None,
            api_version: str | None = None) -> CachedFetcher:
    client = client or HttpClient(min_interval_s=0.5, timeout_s=90)
    return CachedFetcher(conn, "chembl", BASE, client,
                         api_version=api_version or chembl_version(client))


def molecules_by_inchikey(f: CachedFetcher, inchikey: str) -> list[dict]:
    """Exact full-InChIKey lookup. Never query on the first block alone."""
    if len(inchikey) != 27:
        raise ValueError(f"full 27-char InChIKey required, got {inchikey!r}")
    status, data = f.get_json("molecule.json",
                              {"molecule_structures__standard_inchi_key": inchikey})
    return data["molecules"] if status == 200 else []


def atc_codes(molecule: dict) -> list[str]:
    return sorted(molecule.get("atc_classifications") or [])


def parent_chembl_id(molecule: dict) -> str | None:
    h = molecule.get("molecule_hierarchy") or {}
    return h.get("parent_chembl_id")
