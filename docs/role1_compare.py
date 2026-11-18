"""Compare the two readers' role labels and the resolver's suggestions (docs/role1_protocol.md)."""
import csv
import math
import sys
from collections import Counter
from pathlib import Path

import yaml

root = Path(__file__).resolve().parent.parent
LABELS = ["experimental", "comparator", "background", "unclear"]
load = lambda who: {r["id"]: r for r in yaml.safe_load(open(root / "data" / "reviews" / f"role1_labels_{who}.yaml",
                                                            encoding="utf-8"))["rows"]}
a, b = load("claude"), load("kevin")
for who, d in (("claude", a), ("kevin", b)):
    bad = [i for i, r in d.items() if r["label"] not in LABELS]
    if bad:
        sys.exit(f"{who}: missing/invalid labels for ids {bad}")
ids = sorted(a)
n = len(ids)
agree = sum(a[i]["label"] == b[i]["label"] for i in ids)
pa, pb = Counter(a[i]["label"] for i in ids), Counter(b[i]["label"] for i in ids)
pe = sum(pa[l] * pb[l] for l in LABELS) / (n * n)
po = agree / n
kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
band = "Reliable" if kappa >= 0.8 else "Moderate" if kappa >= 0.6 else "Not reliable"
print(f"n={n}  raw agreement {agree}/{n} = {po:.1%}  Cohen's kappa = {kappa:.3f}  -> {band}")
print("confusion (rows Claude, cols Kevin):")
print("".ljust(14) + "".join(l[:12].ljust(14) for l in LABELS))
for la in LABELS:
    print(la[:12].ljust(14) + "".join(str(sum(1 for i in ids if a[i]["label"] == la and b[i]["label"] == lb)).ljust(14)
                                      for lb in LABELS))
with open(root / "data" / "measurements" / "role1_resolver_roles.csv", newline="") as fh:
    res = {(r["nct_id"], int(r["idx"]), r["compound_key"]): r["resolver_role"] for r in csv.DictReader(fh)}
def wilson(k, m, z=1.96):
    if not m: return (float("nan"),) * 2
    p = k / m; d = 1 + z * z / m; c = (p + z * z / (2 * m)) / d
    h = z * math.sqrt(p * (1 - p) / m + z * z / (4 * m * m)) / d
    return c - h, c + h
def acc(ref):
    rows = [i for i in ids if ref(i) not in (None, "unclear")]
    k = sum(res[(a[i]["nct_id"], a[i]["intervention_index"], a[i]["compound"])] == ref(i) for i in rows)
    lo, hi = wilson(k, len(rows))
    return f"{k}/{len(rows)} = {k / len(rows):.1%} (Wilson 95% {lo:.1%}-{hi:.1%})" if rows else "n/a"
print("resolver accuracy, rows both agree (excl. unclear):", acc(lambda i: a[i]["label"] if a[i]["label"] == b[i]["label"] else None))
print("resolver accuracy vs Claude:", acc(lambda i: a[i]["label"]))
print("resolver accuracy vs Kevin: ", acc(lambda i: b[i]["label"]))
print("\nDISAGREEMENTS (evidence of underspecified rules, not errors to resolve):")
for i in ids:
    if a[i]["label"] != b[i]["label"]:
        print(f"  #{i} {a[i]['nct_id']} {a[i]['compound']}: Claude={a[i]['label']} | Kevin={b[i]['label']}")
        print(f"      Claude: {a[i].get('note', '')}\n      Kevin:  {b[i].get('note', '')}")
