"""Raw layer → normalised layer.

Compound resolution is not done here: callers pass the mapping from source
compound strings to compound_id (from the fixture now, from the resolver later).
"""
from __future__ import annotations

import sqlite3

from agesdk.evidence import (DIRECTION_RULE_VERSION, direction_of_drugage_row,
                             evidence_key, sex_of_drugage_row)


def _num(x):
    try:
        return float(str(x).strip())
    except (TypeError, ValueError):
        return None


def _sig(x):
    x = (x or "").strip().upper()
    return x if x in ("S", "NS") else None


def _text(x):
    x = (x or "").strip()
    return x or None


def load_drugage_evidence(conn: sqlite3.Connection, raw_response_id: int, rows: list[dict],
                          compound_ids: dict[str, int]) -> int:
    """Insert animal_evidence for rows whose compound_name is mapped. Idempotent
    (UNIQUE raw_response_id + source_row_number). Returns rows inserted."""
    inserted = 0
    for i, r in enumerate(rows, start=1):
        cid = compound_ids.get(r["compound_name"])
        if cid is None:
            continue
        d = direction_of_drugage_row(r)
        cur = conn.execute(
            """INSERT OR IGNORE INTO animal_evidence (
                 compound_id, species, strain, sex, dosage, age_at_initiation, treatment_duration,
                 avg_lifespan_change_pct, avg_lifespan_significance,
                 max_lifespan_change_pct, max_lifespan_significance,
                 weight_change_pct, weight_change_significance,
                 avg_direction, max_direction, direction, direction_conflict, direction_rule_version,
                 evidence_key, is_itp, pmid, source, source_compound_name,
                 raw_response_id, source_row_number)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'drugage', ?, ?, ?)""",
            (cid, r["species"], _text(r["strain"]), sex_of_drugage_row(r), _text(r["dosage"]),
             _text(r["age_at_initiation"]), _text(r["treatment_duration"]),
             _num(r["avg_lifespan_change_percent"]), _sig(r["avg_lifespan_significance"]),
             _num(r["max_lifespan_change_percent"]), _sig(r["max_lifespan_significance"]),
             _num(r["weight_change_percent"]), _sig(r["weight_change_significance"]),
             d.avg, d.max, d.combined, int(d.conflict), DIRECTION_RULE_VERSION,
             evidence_key("drugage", r), int(r["ITP"].strip() == "Yes"), _text(r["pubmed_id"]),
             r["compound_name"], raw_response_id, i))
        inserted += cur.rowcount
    conn.commit()
    return inserted

