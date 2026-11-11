"""Hand-curated reference data that lives in the repo (data/reference/)."""
from __future__ import annotations

import sqlite3

from agesdk.fixture import SPECIES_PATH
import csv


def load_species(conn: sqlite3.Connection, path=SPECIES_PATH) -> int:
    """Upsert data/reference/species_taxon.csv into species_taxon. Idempotent."""
    with open(path, encoding="utf-8", newline="") as fh:
        rows = [(r["species"], r["tier"], r.get("ncbi_taxid") or None, r.get("note") or None)
                for r in csv.DictReader(fh)]
    conn.executemany(
        """INSERT INTO species_taxon (species, tier, ncbi_taxid, note) VALUES (?, ?, ?, ?)
           ON CONFLICT (species) DO UPDATE SET tier = excluded.tier,
             ncbi_taxid = excluded.ncbi_taxid, note = excluded.note""", rows)
    conn.commit()
    return len(rows)
