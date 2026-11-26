"""Intervention-string resolver (SPEC §5.1a, §7 step 3).

Maps registry intervention strings to fixture compounds, deliberately conservatively:

* **Primary evidence** is an intervention object's ``name`` and ``otherNames``. Only a
  *clean* primary match is auto-accepted: after stripping doses, formulation and salt
  words, the string equals a fixture synonym. Anything else that mentions the compound
  (a combination, a qualified phrase, a typo, a short code) goes to review.
* **Weak evidence** is an intervention description (review) or study-level text — arm
  descriptions, titles, summary — which yields at most a ``background_candidate``.
* **Registry search membership is never evidence.** A study hit by a query but naming the
  compound nowhere gets no row.
* **Class-level names** ("SGLT2 inhibitor") and multi-drug otherNames lists go to review.
* Fixture ``must_not_match`` strings reject; ``needs_review`` strings force review; a
  placebo matching the compound is rejected as "placebo_matching".

Each row also carries a suggested role (§5.9, from arm groups) and a systemic-exposure
classification (§5.6). Nothing here writes to trial_intervention: decisions stay in
resolver_match until reviewed (§7 step 4).
"""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import yaml

from agesdk.db import PROJECT_ROOT

RULES_PATH = PROJECT_ROOT / "data" / "rules" / "resolver.yaml"
DASHES = dict.fromkeys(map(ord, "‐‑‒–—−"), "-")
COMPARATOR_ARM_TYPES = {"PLACEBO_COMPARATOR", "ACTIVE_COMPARATOR", "SHAM_COMPARATOR", "NO_INTERVENTION"}


def load_rules(path=RULES_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _lev1(a: str, b: str) -> bool:
    """True if edit distance is exactly 1."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


@dataclass
class Match:
    compound: str
    method: str            # exact | normalised | contains | fuzzy | short_code | review_list | negative
    term: str
    reasons: list = field(default_factory=list)


_WORD = re.compile(r"\w+")


class Resolver:
    def __init__(self, fx: dict, rules: dict | None = None, use_index: bool = True):
        self.rules = rules or load_rules()
        self.version = self.rules["version"]
        r = self.rules
        self._dose = re.compile(r["dose_pattern"], re.IGNORECASE)
        self._drop = {w.lower() for w in r["formulation_words"] + r["salt_words"]}
        self._placebo = re.compile(r["placebo_pattern"])
        self._class = [re.compile(p) for p in r["class_patterns"]]
        self._generic = [re.compile(p) for p in r["generic_name_patterns"]]
        self._local = [re.compile(p) for p in r["local_route_patterns"]]
        self._unclear = [re.compile(p) for p in r["unclear_route_patterns"]]
        self._systemic = [re.compile(p) for p in r["systemic_route_patterns"]]
        self.short = r["short_code_max_len"]
        self._desc_disq = {k: re.compile(v) for k, v in r.get("description_disqualifiers", {}).items()}
        self._other_stems = re.compile("|".join(r.get("other_drug_stems", [])) or r"(?!)")
        self._combo_name = re.compile(r.get("combination_name_pattern") or r"(?!)")
        self.fuzzy_min = r["fuzzy_min_len"]
        self.compounds = {}
        for c in fx["compounds"]:
            syn = {self.normalise(s) for s in [c["canonical_name"]] + list(c["must_match"])} - {""}
            self.compounds[c["key"]] = {
                "syn": syn,
                "syn_stripped": {self.strip(s) for s in syn} - {""},
                "neg": {self.normalise(s) for s in c.get("must_not_match", [])} - {""},
                "review": {self.normalise(s) for s in c.get("needs_review", [])} - {""},
                "route_local": {self.normalise(s) for s in c.get("route_excluded", [])} - {""},
                # D2 (docs/synonym_pipeline.md): no edit-distance near-misses for scaled compounds
                "fuzzy": c.get("role") != "scaled",
            }
        self._rx: dict[str, re.Pattern] = {}
        # Word index (D4, exact, no behaviour change). A term can only match where its first
        # \w+ run occurs as a whole \w+ run of the text: the pattern is (?<!\w)term(?!\w), so the
        # characters around that run are either the term's own non-word characters or the
        # pattern's boundaries. So a compound none of whose terms' first runs occur in the text
        # cannot produce a syn / neg / review span there, and the full evaluation is skipped.
        self.use_index = use_index
        self._index: dict[str, set] = defaultdict(set)
        self._always: set = set()                 # compounds with a term containing no \w at all
        for key, d in self.compounds.items():
            for term in d["syn"] | d["neg"] | d["review"]:
                m = _WORD.search(term)
                if m:
                    self._index[m.group(0)].add(key)
                else:
                    self._always.add(key)

    # ---------------------------------------------------------------- text
    @staticmethod
    def normalise(text) -> str:
        t = unicodedata.normalize("NFKC", str(text or "")).translate(DASHES).lower()
        t = re.sub(r"[®™©]", " ", t)
        t = re.sub(r"[^\w\s/+\-.%]", " ", t)
        return " ".join(t.split())

    def strip(self, n: str) -> str:
        t = self._dose.sub(" ", n)
        toks = [w for w in re.split(r"\s+", t) if w and w.strip(".-") not in self._drop]
        return " ".join(toks).strip(" .-/+")

    def _phrase(self, term: str) -> re.Pattern:
        rx = self._rx.get(term)
        if rx is None:
            rx = self._rx[term] = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)")
        return rx

    def _spans(self, n: str, terms) -> list[tuple[int, int, str]]:
        """Occurrences of any of ``terms`` (one combined pattern per term set, longest first)."""
        key = frozenset(terms)
        rx = self._rx.get(key)
        if rx is None:
            alts = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
            rx = self._rx[key] = re.compile(r"(?<!\w)(?:" + alts + r")(?!\w)") if terms else None
        return [(m.start(), m.end(), m.group(0)) for m in rx.finditer(n)] if rx else []

    @staticmethod
    def _inside(span, others) -> bool:
        return any(o[0] <= span[0] and span[1] <= o[1] and (o[0], o[1]) != (span[0], span[1]) for o in others)

    # ---------------------------------------------------------------- matching
    def match(self, text) -> list[Match]:
        """Every fixture compound this string bears on, with the method."""
        n = self.normalise(text)
        if not n:
            return []
        st = self.strip(n)
        out = []
        if self.use_index:
            cand = set(self._always)
            for w in _WORD.findall(n):
                cand |= self._index.get(w, set())
        for key, d in self.compounds.items():
            if self.use_index and key not in cand:
                # No term of this compound can occur in n: only the near-miss step can apply.
                if d["fuzzy"]:
                    hit = self._near_miss(st, d)
                    if hit:
                        out.append(Match(key, "fuzzy", hit[1], [f"near_miss:{hit[0]}"]))
                continue
            syn = self._spans(n, d["syn"])
            neg = self._spans(n, d["neg"])
            rev = self._spans(n, d["review"])
            syn_ok = [s for s in syn if not self._inside(s, neg)]
            neg_ok = [s for s in neg if not any(o[0] <= s[0] and s[1] <= o[1] for o in syn)]
            rev_ok = [s for s in rev if not any(o[0] <= s[0] and s[1] <= o[1] and o != s for o in syn)]
            if neg_ok and not syn_ok:
                out.append(Match(key, "negative", neg_ok[0][2], ["must_not_match"]))
            elif rev_ok:
                out.append(Match(key, "review_list", rev_ok[0][2], ["needs_review_list"]))
            elif syn_ok:
                term = max(syn_ok, key=lambda s: s[1] - s[0])[2]
                residue = n
                for a, b, _ in sorted(syn_ok, reverse=True):
                    residue = residue[:a] + " " + residue[b:]
                self_only = not self.strip(" ".join(residue.split()))
                if st in d["syn_stripped"] or self_only:
                    if st in d["syn_stripped"] and len(st) <= self.short:
                        out.append(Match(key, "short_code", term, ["short_code"]))
                    else:
                        out.append(Match(key, "exact" if n in d["syn"] else "normalised", term,
                                         [] if st in d["syn_stripped"] else ["only_own_synonyms"]))
                else:
                    out.append(Match(key, "contains", term, ["qualified_or_combination"]))
            elif d["fuzzy"]:
                hit = self._near_miss(st, d)
                if hit:
                    out.append(Match(key, "fuzzy", hit[1], [f"near_miss:{hit[0]}"]))
        return out

    def _near_miss(self, st: str, d: dict):
        singles = [s for s in d["syn_stripped"] if " " not in s and len(s) >= self.fuzzy_min]
        return next(((tok, s) for tok in st.split() if len(tok) >= self.fuzzy_min
                     for s in singles if _lev1(tok, s)), None)

    def is_class_level(self, n: str) -> bool:
        return any(p.search(n) for p in self._class)

    def is_generic(self, n: str) -> bool:
        return any(p.fullmatch(n) for p in self._generic)

    # ---------------------------------------------------------------- route, role
    def route(self, iv: dict, compound: str, context: str = "") -> tuple[str, str]:
        """Route from the intervention's own text; if that has no route word, from ``context``
        (the arm descriptions it belongs to and the study title), labelled as such."""
        kind, basis = self._route_text(iv, compound, self.normalise(" ".join(
            [iv.get("name") or "", " ".join(iv.get("otherNames") or []), iv.get("description") or ""])))
        if basis.startswith("default") and context:
            k2, b2 = self._route_text({}, compound, self.normalise(context))
            if not b2.startswith("default"):
                return k2, b2 + " (study/arm text)"
        return kind, basis

    def _route_text(self, iv: dict, compound: str, text: str) -> tuple[str, str]:
        for t in self.compounds[compound]["route_local"]:
            if self._phrase(t).search(text):
                return "local", f"fixture route_excluded: {t}"
        for kind, pats in (("local", self._local), ("unclear", self._unclear), ("systemic", self._systemic)):
            for p in pats:
                m = p.search(text)
                if m:
                    return kind, f"route word: {m.group(0)}"
        if (iv.get("type") or "") in self.rules["local_intervention_types"]:
            return "local", f"intervention type {iv.get('type')}"
        return "systemic", "default for intervention type " + (iv.get("type") or "unknown")

    @staticmethod
    def role(iv: dict, arms: list[dict]) -> tuple[str, str]:
        if not arms:
            return "unclear", "no arm groups"
        labels = set(iv.get("armGroupLabels") or [])
        types = {a.get("label"): (a.get("type") or "") for a in arms}
        mine = {types[l] for l in labels if l in types}
        if len(arms) == 1:
            return "experimental", "single-arm study"
        if labels >= set(types) and len(types) >= 2:
            if set(types.values()) & COMPARATOR_ARM_TYPES:
                return "background", "given in every arm, including a comparator arm"
            return "experimental", "given in every arm, all arms experimental (dose or regimen comparison)"
        if "EXPERIMENTAL" in mine:
            return "experimental", "in an EXPERIMENTAL arm"
        if mine and mine <= {"ACTIVE_COMPARATOR"}:
            return "comparator", "in ACTIVE_COMPARATOR arm(s) only"
        return "unclear", f"arm types {sorted(mine) or 'none linked'}"

    # ---------------------------------------------------------------- per intervention
    def resolve_intervention(self, iv: dict, arms: list[dict], title: str = "") -> list[dict]:
        name = iv.get("name") or ""
        n_name = self.normalise(name)
        placebo = bool(self._placebo.search(n_name))
        # A placebo FOR the compound ("X-matching placebo", "placebo of X", "dummy X") is not the
        # compound. "X and placebo" may be X given with another drug's placebo: review instead.
        placebo_for = placebo and bool(re.search(r"\b(matching|match|dummy|sham|vehicle)\b", n_name)
                                       or self.is_leading_placebo_for(n_name))
        class_level = self.is_class_level(n_name)
        generic = self.is_generic(n_name)
        by_field = {"name": {m.compound: m for m in self.match(name)}}
        # Across an otherNames list, keep each compound's strongest evidence: one entry being a
        # must_not_match (e.g. "Dapagliflozin" for empagliflozin) must not hide another entry
        # naming the compound ("Empagliflozin").
        rank = {"exact": 0, "normalised": 0, "review_list": 1, "contains": 2, "short_code": 3,
                "fuzzy": 4, "negative": 9}
        other_hits: dict[str, Match] = {}
        other_compounds = set()
        for o in iv.get("otherNames") or []:
            for m in self.match(o):
                if m.method != "negative":
                    other_compounds.add(m.compound)
                if m.compound not in other_hits or rank[m.method] < rank[other_hits[m.compound].method]:
                    other_hits[m.compound] = m
        by_field["other_names"] = other_hits
        by_field["description"] = {m.compound: m for m in self.match(iv.get("description"))}
        n_desc = self.normalise(iv.get("description"))
        combo_name = bool(self._combo_name.search(n_name))
        rows = []
        for key in set().union(*[set(v) for v in by_field.values()]):
            m_name, m_other, m_desc = (by_field[f].get(key) for f in ("name", "other_names", "description"))
            if (m_name and m_name.method in ("short_code", "contains", "fuzzy") and m_other
                    and m_other.method in ("exact", "normalised") and len(other_compounds) == 1
                    and not combo_name):
                fld, m, strength = "other_names", m_other, "primary"
                m = Match(m.compound, m.method, m.term, m.reasons + ["name_and_other_names_agree"])
                generic_ok = True
            elif m_name:
                generic_ok = False
                fld, m, strength = "name", m_name, "primary"
            elif m_other:
                generic_ok = False
                fld, m, strength = "other_names", m_other, "primary"
            else:
                generic_ok = False
                fld, m, strength = "description", m_desc, "weak"
            reasons = list(m.reasons)
            if m.method == "negative":
                decision = "rejected"
            elif placebo_for or (m_name and self.is_x_placebo(key, n_name)):
                decision, reasons = "rejected", reasons + ["placebo_matching"]
            elif placebo:
                decision, reasons = "review", reasons + ["placebo_with_compound"]
            elif strength == "weak":
                decision, reasons = "review", reasons + ["weak_evidence_description"]
            elif m.method not in ("exact", "normalised"):
                decision = "review"
            elif class_level:
                decision, reasons = "review", reasons + ["class_level_name"]
            elif fld == "other_names" and len(other_compounds) > 1:
                decision, reasons = "review", reasons + ["multi_compound_other_names"]
            elif fld == "other_names" and not (generic or generic_ok):
                decision, reasons = "review", reasons + ["other_names_behind_specific_name"]
            else:
                decision = "auto_accept"
                if fld == "other_names":
                    reasons.append("other_names_behind_generic_name")
            if decision == "auto_accept":
                # Disqualifiers only: each can move auto_accept to review, never the reverse.
                why = self._disqualify(key, iv, n_desc)
                if why:
                    decision, reasons = "review", reasons + why
            # The asymmetry, enforced: acceptance only ever rests on name / otherNames.
            assert not (decision == "auto_accept" and strength != "primary"), "description cannot accept"
            role, role_basis = self.role(iv, arms)
            mine = set(iv.get("armGroupLabels") or [])
            context = " ".join([title] + [(a.get("label") or "") + " " + (a.get("description") or "")
                                          for a in arms if a.get("label") in mine])
            route, route_basis = self.route(iv, key, context)
            evidence_text = {"name": name, "other_names": next(
                (o for o in iv.get("otherNames") or [] if any(x.compound == key for x in self.match(o))), ""),
                "description": ""}[fld]
            is_combination = self.is_combination(key, evidence_text, n_desc)
            rows.append({"compound_key": key, "evidence_field": fld, "evidence_strength": strength,
                         "is_combination": is_combination,
                         "matched_text": {"name": name, "other_names": " | ".join(iv.get("otherNames") or []),
                                          "description": (iv.get("description") or "")[:500]}[fld],
                         "matched_term": m.term, "method": m.method, "decision": decision,
                         "reasons": reasons, "role": role, "role_basis": role_basis,
                         "systemic_exposure": route, "route_basis": route_basis})
        return rows

    def is_leading_placebo_for(self, n_name: str) -> bool:
        """A name starting with "placebo". v1-v4 rejected all of them; resolver-v5 rejects
        only a placebo FOR something: "Placebo", "Placebo tablets", "placebo of / for / to X".
        "Placebo + Metformin", "Placebo plus metformin IR", "Placebo with mood stabilizer
        (lithium or divalproex)" administer the compound alongside another drug's placebo:
        placebo_with (review). Moves rejected -> review only; review can never auto-accept."""
        stripped = self.strip(n_name)
        if not re.match(r"placebos?\b", stripped):
            return False
        if re.match(r"placebos?\s+(of|for|to)\b", stripped):
            return True
        return not re.search(r"\+|\bplus\b|\bwith\b|\band\b|\bbackground\b", stripped)

    def is_x_placebo(self, key: str, n_name: str) -> bool:
        """resolver-v4: the name is "<this compound> placebo" and nothing else ("ASA placebo",
        "Empagliflozin high placebo", "Metformin DR Placebo"): a placebo FOR the compound.
        Anything left over ("then", "vs", "followed by", another drug) keeps it out, so
        sequences and "X and placebo" stay in review. Downgrade only: review -> rejected."""
        stripped = self.strip(n_name)
        if not re.search(r"\bplacebos?$", stripped) or self._combo_name.search(stripped):
            return False                                   # "X + placebo", "X/placebo": review
        residue = stripped
        for a, b, _ in sorted(self._spans(stripped, self.compounds[key]["syn"]), reverse=True):
            residue = residue[:a] + " " + residue[b:]
        residue = re.sub(r"\b(placebos?|matched|matching)\b|[-()]", " ", residue)
        return residue != stripped.replace("-", " ") and not self.strip(" ".join(residue.split()))

    def is_combination(self, key: str, text: str, n_desc: str) -> bool:
        """The compound given as part of a combination: a name joining it with another drug
        ("Metformin + Sitagliptin", "Saxagliptin/Metformin"), or a description stating a
        fixed-dose combination. Bracketed detail ("(NIAGEN TM, ChromaDex, CA, USA)") is not a
        second drug, so separators inside brackets do not count."""
        if "fixed_combination" in self._desc_disq and self._desc_disq["fixed_combination"].search(n_desc or ""):
            return True
        n = self.normalise(re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", text or ""))
        n = " ".join(self._dose.sub(" ", n).split())          # "100 mg/d" is a dose, not a separator
        if not n or not self._combo_name.search(n):
            return False
        residue = n
        for a, b, _ in sorted(self._spans(n, self.compounds[key]["syn"]), reverse=True):
            residue = residue[:a] + " " + residue[b:]
        residue = re.sub(r"[/+&,]|\band\b|\bwith\b|\bplus\b|\bplacebo\b|\bmatching\b", " ", residue)
        return bool(self.strip(" ".join(residue.split())))

    def _disqualify(self, key: str, iv: dict, n_desc: str) -> list[str]:
        """Reasons an otherwise clean match must go to review (resolver-v2). Downgrade only."""
        why = [f"description_{k}" for k, rx in self._desc_disq.items() if rx.search(n_desc)]
        d = self.compounds[key]
        if n_desc and self._spans(n_desc, d["review"] | d["neg"]):
            why.append("description_fixture_list")
        for o in iv.get("otherNames") or []:
            mine = {m.compound for m in self.match(o) if m.method != "negative"}
            if key in mine:
                continue                       # names the matched compound itself (a brand, a code)
            if mine or self._other_stems.search(self.normalise(o)):
                why.append("other_names_list_other_drugs")
                break
        return why

    def resolve_study_text(self, arms: list[dict], texts: list[str], exclude: set[str]) -> list[dict]:
        """Study-level weak evidence for compounds no intervention object names."""
        arm_text = " | ".join((a.get("label") or "") + ": " + (a.get("description") or "") for a in arms)
        found = {}
        for fld, text in (("arm_group", arm_text), ("title_summary", " | ".join(t for t in texts if t))):
            for m in self.match(text):
                if m.compound in exclude or m.compound in found or m.method in ("negative", "fuzzy"):
                    continue
                found[m.compound] = {"compound_key": m.compound, "evidence_field": fld, "evidence_strength": "weak",
                                     "matched_text": text[:500], "matched_term": m.term, "method": m.method,
                                     "decision": "background_candidate", "reasons": m.reasons + ["study_text_only"],
                                     "role": "background", "role_basis": "named only in study-level text",
                                     "systemic_exposure": None, "route_basis": None}
        return list(found.values())


# ---------------------------------------------------------------- run over staging

def _study_texts(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Official title and brief summary per staged study, read once from the raw pages."""
    wanted = {r[0] for r in conn.execute("SELECT nct_id FROM ctgov_study")}
    raw_ids = {r[0] for r in conn.execute("SELECT DISTINCT raw_response_id FROM ctgov_study")}
    out = {}
    cur = conn.cursor()
    for rid, body in cur.execute(f"SELECT id, response_body FROM raw_response WHERE id IN "
                                 f"({','.join('?' * len(raw_ids))})", tuple(raw_ids)) if raw_ids else []:
        for s in json.loads(body).get("studies", []):
            ps = s["protocolSection"]
            nct = ps["identificationModule"]["nctId"]
            if nct in wanted:
                out[nct] = [ps["identificationModule"].get("officialTitle"),
                            ps.get("descriptionModule", {}).get("briefSummary")]
    return out


def _snapshot(conn) -> dict:
    return {(r[0], r[1], r[2]): {"decision": r[3], "is_combination": bool(r[4]), "version": r[5], "text": r[6]}
            for r in conn.execute("SELECT nct_id, idx, compound_key, decision, is_combination, resolver_version, "
                                  "matched_text FROM resolver_match")}


def diff(old: dict, new: dict, examples: int = 8) -> dict:
    """What a resolver change did, row by row (docs/measurement_policy.md §3: every resolver
    change is checked against the previous decisions before it is committed). A row is
    (nct_id, idx, compound_key). New auto-accepts are the rows that make a change NOT
    downgrade-only: an auto-accept now that was not one before, including on a new row."""
    both = old.keys() & new.keys()
    trans = defaultdict(list)
    for k in sorted(both):
        a, b = old[k]["decision"], new[k]["decision"]
        if a != b:
            trans[f"{a}->{b}"].append(k)
    added, gone = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    new_aa = [k for k in both if new[k]["decision"] == "auto_accept" and old[k]["decision"] != "auto_accept"]
    new_aa += [k for k in added if new[k]["decision"] == "auto_accept"]
    ex = lambda ks, src: [f"{k[0]} #{k[1]} {k[2]}: {src[k]['text'][:70]}" for k in ks[:examples]]
    count = lambda rows, d: sum(r["decision"] == d for r in rows.values())
    return {
        "from_version": sorted({r["version"] for r in old.values()}),
        "to_version": sorted({r["version"] for r in new.values()}),
        "auto_accept": [count(old, "auto_accept"), count(new, "auto_accept")],
        "review": [count(old, "review"), count(new, "review")],
        "new_auto_accepts": len(new_aa), "new_auto_accept_examples": ex(sorted(new_aa), new),
        "transitions": {t: {"rows": len(ks), "examples": ex(ks, new)} for t, ks in sorted(trans.items())},
        "rows_added": {"rows": len(added), "by_decision": dict(Counter(new[k]["decision"] for k in added)),
                       "examples": ex(added, new)},
        "rows_gone": {"rows": len(gone), "by_decision": dict(Counter(old[k]["decision"] for k in gone)),
                      "examples": ex(gone, old)},
        "is_combination": {"0->1": sum(1 for k in both if new[k]["is_combination"] and not old[k]["is_combination"]),
                           "1->0": sum(1 for k in both if old[k]["is_combination"] and not new[k]["is_combination"])},
    }


class NotDowngradeOnly(Exception):
    """A run declared downgrade-only produced a new auto-accept; nothing was committed."""

    def __init__(self, report: dict):
        super().__init__(f"{report['new_auto_accepts']} new auto-accept(s): {report['new_auto_accept_examples']}")
        self.report = report


def run(conn: sqlite3.Connection, fx: dict, rules: dict | None = None, downgrade_only: bool = False) -> dict:
    """Rebuild resolver_match and report the diff against the previous decisions. With
    downgrade_only=True, any new auto-accept rolls the whole run back (NotDowngradeOnly)."""
    res = Resolver(fx, rules)
    before = _snapshot(conn)
    conn.execute("DELETE FROM resolver_match")
    texts = _study_texts(conn)
    ivs = defaultdict(list)
    for r in conn.execute("SELECT nct_id, idx, object_json FROM ctgov_intervention ORDER BY nct_id, idx"):
        ivs[r[0]].append((r[1], json.loads(r[2])))
    n_rows = 0
    for nct, title, arms_json in conn.execute("SELECT nct_id, brief_title, arm_groups FROM ctgov_study").fetchall():
        arms = json.loads(arms_json) if arms_json else []
        named = set()
        for idx, iv in ivs.get(nct, []):
            for row in res.resolve_intervention(iv, arms, title or ""):
                if row["decision"] != "rejected":
                    named.add(row["compound_key"])
                _insert(conn, nct, idx, row, res.version)
                n_rows += 1
        for row in res.resolve_study_text(arms, [title] + texts.get(nct, []), exclude=named):
            _insert(conn, nct, -1, row, res.version)
            n_rows += 1
    report = diff(before, _snapshot(conn)) if before else None
    if downgrade_only and report and report["new_auto_accepts"]:
        conn.rollback()
        raise NotDowngradeOnly(report)
    conn.commit()
    return {"resolver_version": res.version, "rows": n_rows, "diff": report}


def _insert(conn, nct, idx, row, version):
    conn.execute(
        """INSERT OR REPLACE INTO resolver_match (nct_id, idx, compound_key, evidence_field, evidence_strength,
             matched_text, matched_term, method, decision, reasons, role, role_basis, systemic_exposure,
             route_basis, is_combination, resolver_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (nct, idx, row["compound_key"], row["evidence_field"], row["evidence_strength"], row["matched_text"],
         row["matched_term"], row["method"], row["decision"], json.dumps(row["reasons"]), row["role"],
         row["role_basis"], row["systemic_exposure"], row["route_basis"], int(row.get("is_combination", False)),
         version))


# ---------------------------------------------------------------- fixture evaluation

def evaluate_fixture(fx: dict, rules: dict | None = None) -> dict:
    """Score the resolver on the fixture's own lists, each string tested as an intervention name.

    Hard failures (must be zero): a must_not_match or needs_review string auto-accepted for
    its compound; a must_match string auto-accepted for a DIFFERENT compound; a
    route_excluded string classed as systemic. must_match strings may land in review: that
    costs recall, not precision, and is reported.
    """
    res = Resolver(fx, rules)
    out = {"must_match": Counter(), "violations": [], "must_match_review": []}
    for c in fx["compounds"]:
        k = c["key"]
        for s in c["must_match"]:
            rows = {r["compound_key"]: r for r in res.resolve_intervention({"name": s, "type": "DRUG"}, [])}
            mine = rows.get(k)
            out["must_match"][mine["decision"] if mine else "missed"] += 1
            if mine and mine["decision"] == "review":
                out["must_match_review"].append((k, s, mine["method"], mine["reasons"]))
            if not mine:
                out["must_match_review"].append((k, s, "missed", []))
            for other, r in rows.items():
                if other != k and r["decision"] == "auto_accept":
                    out["violations"].append(f"{k}: must_match {s!r} auto-accepted as {other}")
        for lst in ("must_not_match", "needs_review"):
            for s in c.get(lst, []):
                rows = {r["compound_key"]: r for r in res.resolve_intervention({"name": s, "type": "DRUG"}, [])}
                if rows.get(k, {}).get("decision") == "auto_accept":
                    out["violations"].append(f"{k}: {lst} {s!r} auto-accepted")
        for s in c.get("route_excluded", []):
            rows = {r["compound_key"]: r for r in res.resolve_intervention({"name": s, "type": "DRUG"}, [])}
            if rows.get(k, {}).get("systemic_exposure") == "systemic":
                out["violations"].append(f"{k}: route_excluded {s!r} classed systemic")
    out["must_match"] = dict(out["must_match"])
    return out


# ---------------------------------------------------------------- report

def report(conn: sqlite3.Connection, recall_sample: dict | None = None) -> dict:
    """Step-3 measurement over the live staging: per compound, what was auto-accepted (and
    in which role/route), what goes to review and why, what was rejected, and how many
    search hits carry no string evidence at all."""
    out = {}
    plan = defaultdict(set)
    for t, k in conn.execute("SELECT query_term, compound_key FROM ctgov_query_plan"):
        plan[k].add(t)
    for key in sorted(plan):
        q = lambda sql, *a: conn.execute(sql, (key, *a)).fetchall()
        hits = {r[0] for r in conn.execute(
            "SELECT DISTINCT h.nct_id FROM ctgov_query_hit h JOIN ctgov_query_plan p USING (query_term) "
            "WHERE p.compound_key = ?", (key,))}
        rows = q("SELECT nct_id, decision, role, systemic_exposure, reasons FROM resolver_match WHERE compound_key = ?")
        trials = lambda pred: len({r[0] for r in rows if pred(r)})
        reasons = Counter(x for r in rows if r[1] == "review" for x in json.loads(r[4]))
        out[key] = {
            "search_hits": len(hits),
            "auto_accept_trials": trials(lambda r: r[1] == "auto_accept"),
            "auto_experimental_systemic": trials(lambda r: r[1] == "auto_accept" and r[2] == "experimental"
                                                 and r[3] == "systemic"),
            "auto_by_role": dict(Counter(r[2] for r in rows if r[1] == "auto_accept")),
            "auto_local_route": trials(lambda r: r[1] == "auto_accept" and r[3] == "local"),
            "review_trials": trials(lambda r: r[1] == "review"),
            "review_reasons": dict(reasons.most_common(6)),
            "background_candidate_trials": trials(lambda r: r[1] == "background_candidate"),
            "rejected_trials": trials(lambda r: r[1] == "rejected"),
            "search_hit_no_evidence": len(hits - {r[0] for r in rows}),
        }
    if recall_sample:
        caught = [s for s in recall_sample["sample"] if s["eligible"] and s["caught"]]
        res = []
        for s in caught:
            d = [r[0] for r in conn.execute("SELECT decision FROM resolver_match WHERE nct_id = ? AND compound_key = ? "
                                            "ORDER BY idx DESC", (s["nct_id"], s["compound"]))]
            res.append({"nct_id": s["nct_id"], "compound": s["compound"], "registry": s["registry"],
                        "decision": ("auto_accept" if "auto_accept" in d else d[0] if d else "no_row")})
        out["_recall_sample"] = {"caught_by_fetch": len(caught),
                                 "auto_accepted": sum(r["decision"] == "auto_accept" for r in res),
                                 "detail": res}
    return out
