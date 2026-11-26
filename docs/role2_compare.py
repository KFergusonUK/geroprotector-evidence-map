"""Compare role-2 readers and the resolver (docs/role2_protocol.md).

    python3 docs/role2_compare.py      # only after both readers' label files are committed

Readers: claude (all 60), kevin (rows 1..k in packet order; later rows null).
"""
import csv
import math
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import yaml

root = Path(__file__).resolve().parent.parent
REVIEWS = root / "data" / "reviews"
LABELS = ["experimental", "comparator", "background", "unclear"]
READERS = ["claude", "kevin"]
MIN_BANDED = 30


def wilson(k, m, z=1.96):
    if not m:
        return float("nan"), float("nan")
    p = k / m
    d = 1 + z * z / m
    c = (p + z * z / (2 * m)) / d
    h = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d
    return c - h, c + h


def load(who):
    p = REVIEWS / f"role2_labels_{who}.yaml"
    if not p.exists():
        return None
    rows = yaml.safe_load(open(p, encoding="utf-8"))["rows"]
    out, bad = {}, []
    for r in rows:
        lab = r.get("label")
        if lab in (None, ""):
            continue
        lab = str(lab).strip().lower()
        if lab not in LABELS:
            bad.append(r["id"])
        out[r["id"]] = {**r, "label": lab}
    if bad:
        sys.exit(f"{who}: invalid labels for ids {bad}")
    return out


def cohen(x, y, ids):
    n = len(ids)
    agree = sum(x[i]["label"] == y[i]["label"] for i in ids)
    px, py = Counter(x[i]["label"] for i in ids), Counter(y[i]["label"] for i in ids)
    pe = sum(px[l] * py[l] for l in LABELS) / (n * n)
    po = agree / n
    k = (po - pe) / (1 - pe) if pe < 1 else 1.0
    # large-sample SE of kappa (Cohen 1960 approximation), for an indicative interval
    se = math.sqrt(po * (1 - po) / (n * (1 - pe) ** 2)) if pe < 1 else 0.0
    return agree, po, k, (k - 1.96 * se, k + 1.96 * se)


def fleiss(readers, ids):
    m = len(readers)
    if not ids:
        return float("nan")
    tot = Counter()
    P = 0.0
    for i in ids:
        c = Counter(r[i]["label"] for r in readers)
        tot.update(c)
        P += (sum(v * v for v in c.values()) - m) / (m * (m - 1))
    P /= len(ids)
    pe = sum((v / (len(ids) * m)) ** 2 for v in tot.values())
    return (P - pe) / (1 - pe) if pe < 1 else 1.0


def band(k):
    return "Reliable" if k >= 0.8 else "Moderate" if k >= 0.6 else "Not reliable"


def compare():
    data = {w: d for w in READERS if (d := load(w)) is not None}
    print("readers:", {w: len(d) for w, d in data.items()})
    if "kevin" in data:
        ks = sorted(data["kevin"])
        gaps = [i for i in range(1, max(ks) + 1) if i not in data["kevin"]]
        print(f"Kevin labelled rows 1..{max(ks)}" + (f"; SKIPPED ids {gaps} (amendment: rows must not be skipped)"
                                                    if gaps else " in order, none skipped"))
    banded = []
    for a, b in combinations(data, 2):
        ids = sorted(set(data[a]) & set(data[b]))
        if not ids:
            continue
        agree, po, k, (lo, hi) = cohen(data[a], data[b], ids)
        tag = band(k) if len(ids) >= MIN_BANDED else f"not banded (n < {MIN_BANDED})"
        if len(ids) >= MIN_BANDED:
            banded.append((k, a, b))
        print(f"\n{a} vs {b}: n={len(ids)}  raw {agree}/{len(ids)} = {po:.1%}  Cohen's kappa = {k:.3f} "
              f"(approx 95% {lo:.2f}-{hi:.2f})  -> {tag}")
        print(f"  confusion (rows {a}, cols {b}):")
        print("  " + "".ljust(14) + "".join(l[:12].ljust(14) for l in LABELS))
        for la in LABELS:
            print("  " + la[:12].ljust(14) + "".join(
                str(sum(1 for i in ids if data[a][i]["label"] == la and data[b][i]["label"] == lb)).ljust(14)
                for lb in LABELS))
    if len(data) == 3:
        ids3 = sorted(set.intersection(*(set(d) for d in data.values())))
        print(f"\nFleiss' kappa, all three readers, n={len(ids3)}: {fleiss(list(data.values()), ids3):.3f}")
    if banded:
        k, a, b = min(banded)
        print(f"\nFINDING (role-2 bar): kappa = {k:.3f} ({a} vs {b}) -> {band(k)}")
    if "kevin" not in data or len(data["kevin"]) < MIN_BANDED:
        print("FINDING (role-2 bar): fewer than 30 rows labelled by Kevin -> NOT ESTABLISHED "
              "(reported with its interval, no band).")

    with open(root / "data" / "measurements" / "role2_resolver_roles.csv", newline="") as fh:
        res = {(r["nct_id"], int(r["idx"]), r["compound_key"]): r["resolver_role"] for r in csv.DictReader(fh)}
    meta = data["claude"]

    def acc(ref):
        rows = [i for i in sorted(meta) if ref(i) not in (None, "unclear")]
        k = sum(res[(meta[i]["nct_id"], meta[i]["intervention_index"], meta[i]["compound"])] == ref(i) for i in rows)
        lo, hi = wilson(k, len(rows))
        return f"{k}/{len(rows)} = {k / len(rows):.1%} (Wilson 95% {lo:.1%}-{hi:.1%})" if rows else "n/a"

    def all_agree(i):
        labs = {d[i]["label"] for d in data.values() if i in d}
        return labs.pop() if len(labs) == 1 and sum(i in d for d in data.values()) >= 2 else None

    print("\nresolver accuracy, rows where every reader who labelled it agrees (excl. unclear):", acc(all_agree))
    for w, d in data.items():
        print(f"resolver accuracy vs {w}:".ljust(32), acc(lambda i, d=d: d[i]["label"] if i in d else None))

    import re as _re
    for w, d in data.items():
        q = Counter((_re.match(r"\s*Q([1-5])", str(r.get("note") or "")) or [None, "none"])[1] for r in d.values())
        print(f"question that decided the label, {w}:", dict(sorted(q.items())))
    print("\nDISAGREEMENTS (evidence of underspecified rules, not errors to resolve):")
    for i in sorted(meta):
        labs = {w: d[i]["label"] for w, d in data.items() if i in d}
        if len(set(labs.values())) > 1:
            print(f"  #{i} {meta[i]['nct_id']} {meta[i]['compound']}: " + " | ".join(f"{w}={l}" for w, l in labs.items()))
            for w, d in data.items():
                if i in d:
                    print(f"      {w}: {d[i].get('note', '')}")


if __name__ == "__main__":
    compare()
