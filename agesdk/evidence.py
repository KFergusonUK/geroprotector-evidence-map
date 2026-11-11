"""Animal evidence semantics: direction of effect (SPEC §5.4).

Direction is derived per DrugAge row from the significance flags, never from
effect size alone:

1. Average lifespan flagged significant, with a value  -> sign of the average change
2. Otherwise, max lifespan flagged significant, with a value -> sign of the max change
3. Otherwise, any measure flagged non-significant  -> 'null'
4. Otherwise (no significance reported, or a flag with no value) -> 'unassessed'

A significant change of exactly 0 is 'null'. 'unassessed' is not negative
evidence and never counts toward the null cell.
"""
from __future__ import annotations

DIRECTIONS = ("extension", "shortening", "null", "unassessed")
DIRECTION_RULE_VERSION = "direction-v1"


def _num(x) -> float | None:
    if x is None:
        return None
    try:
        return float(str(x).strip())
    except ValueError:
        return None


def _sign(v: float) -> str:
    return "extension" if v > 0 else "shortening" if v < 0 else "null"


def derive_direction(avg_change, avg_sig, max_change, max_sig) -> tuple[str, str]:
    """Return (direction, basis) where basis is 'avg' | 'max' | 'none'."""
    avg, mx = _num(avg_change), _num(max_change)
    avg_sig = (avg_sig or "").strip().upper()
    max_sig = (max_sig or "").strip().upper()
    if avg_sig == "S" and avg is not None:
        return _sign(avg), "avg"
    if max_sig == "S" and mx is not None:
        return _sign(mx), "max"
    if "NS" in (avg_sig, max_sig):
        return "null", "avg" if avg_sig == "NS" else "max"
    return "unassessed", "none"


def direction_of_drugage_row(row: dict) -> tuple[str, str]:
    return derive_direction(row["avg_lifespan_change_percent"], row["avg_lifespan_significance"],
                            row["max_lifespan_change_percent"], row["max_lifespan_significance"])


SEX_MAP = {"male": "M", "female": "F", "pooled": "both", "hermaphrodite": "hermaphrodite"}


def sex_of_drugage_row(row: dict) -> str:
    return SEX_MAP.get(row["gender"].strip().lower(), "unknown")
