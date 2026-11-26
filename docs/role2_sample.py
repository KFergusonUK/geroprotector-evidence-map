"""Draw the role-2 sample (docs/role2_protocol.md) from the FROZEN population file.
Usage: python3 docs/role2_sample.py > sample.json"""
import csv
import json
import random
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
with open(root / "data" / "measurements" / "role2_population.csv", newline="") as fh:
    pop = [(r["nct_id"], int(r["idx"]), r["compound_key"]) for r in csv.DictReader(fh)]
assert len(pop) == 4339, f"population file changed: {len(pop)} rows, protocol froze 4,339"
json.dump(random.Random(20261127).sample(pop, 60), sys.stdout)
