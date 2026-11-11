"""Hit volume and intervention-string quality for the seed fetch (SPEC §7 step 2 report).

Descriptive only: this is not the resolver. A compound is "visible" in a field when
one of its query strings occurs there as a whole word (case-insensitive, dashes
normalised). It answers: how often does the intervention *name* say what the drug is?
"""
from __future__ import annotations

import json
import random
import re
import sqlite3
from collections import Counter, defaultdict

from agesdk.sources.ctgov import normalise_term

FIELDS = ("name", "other_names", "description", "arm_group_labels")


def _pattern(terms: list[str]) -> re.Pattern:
    alts = sorted({re.escape(normalise_term(t).lower()) for t in terms}, key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(alts) + r")(?![a-z0-9])")


JSON_LIST_FIELDS = {"other_names", "arm_group_labels"}


def _text(v, field: str = "name") -> str:
    """Lower-cased, dash-normalised text. Only the list-valued columns hold JSON; a name
    or description may itself start with '[' (e.g. '[18F]FDG')."""
    if v is None:
        return ""
    if field in JSON_LIST_FIELDS:
        v = " | ".join(json.loads(v))
    return normalise_term(str(v)).lower()


def build(conn: sqlite3.Connection, *, sample_per_compound: int = 3, seed: int = 7) -> dict:
    plan = defaultdict(list)
    for term, key in conn.execute("SELECT query_term, compound_key FROM ctgov_query_plan"):
        plan[key].append(term)
    ivs = defaultdict(list)
    for r in conn.execute("SELECT nct_id, name, other_names, description, arm_group_labels, intervention_type "
                          "FROM ctgov_intervention"):
        ivs[r["nct_id"]].append(dict(r))
    rng = random.Random(seed)
    out = {}
    for key, terms in sorted(plan.items()):
        pat = _pattern(terms)
        per_term = {t: n for t, n in conn.execute(
            "SELECT h.query_term, count(*) FROM ctgov_query_hit h JOIN ctgov_query_plan p USING (query_term) "
            "WHERE p.compound_key = ? GROUP BY h.query_term", (key,))}
        studies = [r[0] for r in conn.execute(
            "SELECT DISTINCT h.nct_id FROM ctgov_query_hit h JOIN ctgov_query_plan p USING (query_term) "
            "WHERE p.compound_key = ?", (key,))]
        where = Counter()
        messy = []
        for nct in studies:
            rows = ivs.get(nct, [])
            seen_in = [f for f in FIELDS if any(pat.search(_text(iv[f], f)) for iv in rows)]
            if "name" in seen_in:
                where["name"] += 1
                continue
            first = seen_in[0] if seen_in else "nowhere_in_interventions"
            where[first] += 1
            carrier = [iv for iv in rows if any(pat.search(_text(iv[f], f)) for f in FIELDS[1:])] or rows
            for iv in carrier[:1]:
                messy.append({"nct_id": nct, "found_in": first, "type": iv["intervention_type"],
                              "name": iv["name"],
                              "other_names": json.loads(iv["other_names"]) if iv["other_names"] else []})
        name_counts = Counter((iv["name"] or "").strip() for nct in studies for iv in ivs.get(nct, []))
        out[key] = {
            "query_terms": len(terms),
            "studies": len(studies),
            "fetched_records": sum(1 for n in studies if n in ivs),
            "name_visible": where["name"],
            "not_in_name": len(studies) - where["name"],
            "not_in_name_by_field": {k: v for k, v in where.items() if k != "name"},
            "per_term_hits": dict(sorted(per_term.items(), key=lambda kv: -kv[1])),
            "messy_sample": rng.sample(messy, min(sample_per_compound, len(messy))),
            "top_intervention_names": name_counts.most_common(5),
        }
    return out
