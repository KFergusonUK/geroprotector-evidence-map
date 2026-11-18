"""Draw the step-4b sample (protocol: docs/step4b_precision_protocol.md). Deterministic."""
import json
import random
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agesdk import db  # noqa: E402

SEED, N = 20261119, 200
root = Path(__file__).resolve().parent.parent
done = {(r["nct_id"], r["idx"], r["compound"]) for r in
        yaml.safe_load(open(root / "data" / "reviews" / "step4_precision_sample.yaml", encoding="utf-8"))["rows"]}
conn = db.connect()
rows = [dict(r) for r in conn.execute(
    "SELECT * FROM resolver_match WHERE decision = 'auto_accept' ORDER BY nct_id, idx, compound_key")]
rows = [r for r in rows if (r["nct_id"], r["idx"], r["compound_key"]) not in done]
assert len(rows) == 4783, f"population changed: {len(rows)} rows, protocol froze 4,783"
json.dump(random.Random(SEED).sample(rows, N), sys.stdout, indent=1, ensure_ascii=False)
