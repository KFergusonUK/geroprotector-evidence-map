"""Draw the step-7 samples (docs/step7_precision_protocol.md, frozen-inputs table) from the
FROZEN population file only. Usage: python3 docs/step7_sample.py > sample.json"""
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

root = Path(__file__).resolve().parent.parent
with open(root / "data" / "measurements" / "step7_population.csv", newline="") as fh:
    pop = [dict(r, idx=int(r["idx"])) for r in csv.DictReader(fh)]
assert len(pop) == 10649, f"population file changed: {len(pop)} rows, frozen at 10,649"
key = lambda r: (r["nct_id"], r["idx"], r["compound_key"])

R = random.Random(20261121).sample(pop, 200)

by = defaultdict(list)
for r in pop:                                   # file order within each compound
    by[r["compound_key"]].append(r)
rng = random.Random(20261122)
compounds = rng.sample(sorted(by), min(100, len(by)))
C = [rng.choice(by[k]) for k in compounds]

json.dump({"R": R, "C": C, "R_keys": [key(r) for r in R], "C_keys": [key(r) for r in C]}, sys.stdout)
