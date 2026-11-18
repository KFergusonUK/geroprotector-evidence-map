"""Draw the step-4 precision sample (protocol: docs/step4_precision_protocol.md).

Usage: python3 docs/step4_sample.py > sample.json
Deterministic: same database state, same seed, same 200 rows.
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agesdk import db  # noqa: E402

SEED, N = 20261118, 200

conn = db.connect()
rows = [dict(r) for r in conn.execute(
    "SELECT * FROM resolver_match WHERE decision = 'auto_accept' ORDER BY nct_id, idx, compound_key")]
assert len(rows) == 5252, f"population changed: {len(rows)} rows, protocol froze 5,252"
sample = random.Random(SEED).sample(rows, N)
json.dump(sample, sys.stdout, indent=1, ensure_ascii=False)
