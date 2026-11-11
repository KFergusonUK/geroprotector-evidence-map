"""Animal evidence semantics: direction of effect (SPEC §5.4).

Direction is derived from the significance flags, never from effect size alone,
separately for each measure (average and maximum lifespan):

    significant, with a value  -> sign of the change ('extension' | 'shortening';
                                  a significant change of exactly 0 is 'null')
    not significant            -> 'null'        (measured, no effect detected)
    anything else              -> 'unassessed'  (no significance reported, or a
                                                 flag with no value: NOT negative evidence)

The two measures are then combined symmetrically. There is no precedence of one
measure over the other:

    conflict   -> one measure is significant in one direction and the other measure,
                  also assessed (S or NS), has a point estimate in the opposite
                  direction. E.g. levodopa: mean +7% (NS), max -14% (S). The row is
                  'conflict' and goes to human review; it counts toward no path.
    otherwise  -> the significant direction if any measure is significant (both agree
                  by construction), else 'null' if any measure was assessed, else
                  'unassessed'.

Same direction with different significance (mean +12% S, max +5% NS) is agreement
measured with different power, not a conflict.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

MEASURE_DIRECTIONS = ("extension", "shortening", "null", "unassessed")
DIRECTIONS = MEASURE_DIRECTIONS + ("conflict",)
DIRECTION_RULE_VERSION = "direction-v2"


def _num(x) -> float | None:
    if x is None:
        return None
    try:
        return float(str(x).strip())
    except ValueError:
        return None


def _sig(x) -> str:
    return (x or "").strip().upper()


def measure_direction(change, significance) -> str:
    v, s = _num(change), _sig(significance)
    if s == "S":
        if v is None:
            return "unassessed"
        return "extension" if v > 0 else "shortening" if v < 0 else "null"
    if s == "NS":
        return "null"
    return "unassessed"


@dataclass(frozen=True)
class Direction:
    avg: str
    max: str
    combined: str

    @property
    def conflict(self) -> bool:
        return self.combined == "conflict"


def _opposes(direction: str, value: float | None) -> bool:
    if value is None or value == 0:
        return False
    return (direction == "extension" and value < 0) or (direction == "shortening" and value > 0)


def derive_direction(avg_change, avg_sig, max_change, max_sig) -> Direction:
    avg_d = measure_direction(avg_change, avg_sig)
    max_d = measure_direction(max_change, max_sig)
    avg_v, max_v = _num(avg_change), _num(max_change)
    avg_assessed = _sig(avg_sig) in ("S", "NS")
    max_assessed = _sig(max_sig) in ("S", "NS")

    conflict = ((avg_d in ("extension", "shortening") and max_assessed and _opposes(avg_d, max_v)) or
                (max_d in ("extension", "shortening") and avg_assessed and _opposes(max_d, avg_v)))
    if conflict:
        combined = "conflict"
    else:
        significant = {d for d in (avg_d, max_d) if d in ("extension", "shortening")}
        if significant:
            (combined,) = significant          # both agree, or only one is significant
        elif "null" in (avg_d, max_d):
            combined = "null"
        else:
            combined = "unassessed"
    return Direction(avg_d, max_d, combined)


def direction_of_drugage_row(row: dict) -> Direction:
    return derive_direction(row["avg_lifespan_change_percent"], row["avg_lifespan_significance"],
                            row["max_lifespan_change_percent"], row["max_lifespan_significance"])


SEX_MAP = {"male": "M", "female": "F", "pooled": "both", "hermaphrodite": "hermaphrodite"}


def sex_of_drugage_row(row: dict) -> str:
    return SEX_MAP.get(row["gender"].strip().lower(), "unknown")


def evidence_key(source: str, row: dict) -> str:
    """Stable content hash of a source row. Identical rows share a key, which is
    what a review should attach to: the evidence, not a row number."""
    payload = json.dumps({"source": source, "row": row}, sort_keys=True, ensure_ascii=False)
    return f"{source}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:32]}"
