"""Composition of the resolver's review queue (what kinds of problem it holds).

Each review row is put in exactly one category, by a fixed priority order, so the
categories sum to the queue. Descriptive only: nothing here changes a decision.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict

from agesdk import fixture, resolver

ORDER = [
    ("combination", "is_combination flag: the compound joined with another drug, or a fixed-dose product"),
    ("parenthetical", "clean once bracketed detail is removed, e.g. 'Compound (BRAND, Manufacturer, Location)'"),
    ("class_level", "class-level or regimen name"),
    ("short_code", "abbreviation of 4 characters or fewer"),
    ("near_miss", "edit distance 1 from a synonym (typo or a different word)"),
    ("review_query_or_list", "fixture needs_review string (incl. polyamine review queries, combination brands)"),
    ("description_disqualifier", "clean name, but the description shows an extract, blend, regimen, FDC or listed term"),
    ("other_names_rule", "otherNames-based: specific name with the compound only in otherNames, multi-drug or other-drug lists"),
    ("placebo_with_compound", "'X and placebo'-type name"),
    ("description_only", "named only in the intervention description (weak evidence)"),
    ("qualified_other", "qualified string not covered above"),
]


def _category(row: dict, res: resolver.Resolver) -> str:
    reasons = json.loads(row["reasons"])
    if row["is_combination"]:
        return "combination"
    if row["evidence_field"] in ("name", "other_names") and row["method"] == "contains":
        no_brackets = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", row["matched_text"])
        if any(m.compound == row["compound_key"] and m.method in ("exact", "normalised") for m in res.match(no_brackets)):
            return "parenthetical"
    if "class_level_name" in reasons:
        return "class_level"
    if row["method"] == "short_code":
        return "short_code"
    if row["method"] == "fuzzy":
        return "near_miss"
    if row["method"] == "review_list":
        return "review_query_or_list"
    if any(r.startswith("description_") and r != "description_" for r in reasons) and row["evidence_strength"] == "primary":
        return "description_disqualifier"
    if any(r in reasons for r in ("other_names_behind_specific_name", "multi_compound_other_names",
                                  "other_names_list_other_drugs")):
        return "other_names_rule"
    if "placebo_with_compound" in reasons:
        return "placebo_with_compound"
    if row["evidence_strength"] == "weak":
        return "description_only"
    return "qualified_other"


def characterise(conn: sqlite3.Connection) -> dict:
    res = resolver.Resolver(fixture.load())
    rows = [dict(r) for r in conn.execute("SELECT * FROM resolver_match WHERE decision = 'review'")]
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[_category(r, res)].append(r)
    headline = lambda rs: [r for r in rs if r["role"] == "experimental" and r["systemic_exposure"] == "systemic"
                           and not r["is_combination"]]
    out = {"review_rows": len(rows), "review_trials": len({r["nct_id"] for r in rows}),
           "could_change_headline_rows": len(headline(rows)),
           "could_change_headline_trials": len({r["nct_id"] for r in headline(rows)}), "categories": {}}
    for cat, desc in ORDER:
        rs = by_cat.get(cat, [])
        entry = {"what": desc, "rows": len(rs), "trials": len({r["nct_id"] for r in rs}),
                 "could_change_headline_rows": len(headline(rs)),
                 "by_compound": dict(Counter(r["compound_key"] for r in rs).most_common(5)),
                 "examples": sorted({r["matched_text"][:90] for r in rs})[:6]}
        if cat == "qualified_other":
            words = Counter()
            for r in rs:
                n = res.normalise(re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", r["matched_text"]))
                for a, b, _ in sorted(res._spans(n, res.compounds[r["compound_key"]]["syn"]), reverse=True):
                    n = n[:a] + " " + n[b:]
                words.update(w for w in res.strip(" ".join(n.split())).split() if len(w) > 2)
            entry["leftover_words"] = dict(words.most_common(25))
        out["categories"][cat] = entry
    return out
