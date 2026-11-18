"""Draw the role-1 sample from the FROZEN population file (docs/role1_protocol.md)."""
import csv
import json
import random
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
with open(root / "data" / "measurements" / "role1_population.csv", newline="") as fh:
    pop = [(r["nct_id"], int(r["idx"]), r["compound_key"]) for r in csv.DictReader(fh)]
assert len(pop) == 4556, f"population file changed: {len(pop)}"
json.dump(random.Random(20261120).sample(pop, 100), sys.stdout)
