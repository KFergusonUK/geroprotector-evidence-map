"""Compare the blind verdicts with the original adjudication (docs/step4_precision_result.md).

Agreement on all 30: the number stands. Two or more disagreements: re-adjudicate the whole
sample by someone other than the resolver's author. One: report and resolve by discussion.
"""
import sys
from pathlib import Path

import yaml

root = Path(__file__).resolve().parent.parent
ROUND = sys.argv[1] if len(sys.argv) > 1 else "4"
tag = "step4" if ROUND == "4" else f"step{ROUND}"
blind = yaml.safe_load(open(root / "docs" / f"{tag}_blind_check.yaml", encoding="utf-8"))["rows"]
orig = {r["i"]: r for r in yaml.safe_load(open(root / "data" / "reviews" / f"{tag}_precision_sample.yaml",
                                                encoding="utf-8"))["rows"]}
missing = [b["blind_id"] for b in blind if b["verdict"] not in ("correct", "incorrect")]
if missing:
    sys.exit(f"verdict missing or not 'correct'/'incorrect' for blind_id {missing}")
dis = []
for b in blind:
    o = orig[b["sample_index"]]
    if (b["verdict"] == "correct") != o["identity_correct"]:
        dis.append((b["blind_id"], b["nct_id"], b["verdict"], "correct" if o["identity_correct"] else "incorrect",
                    b.get("note", ""), o.get("note", "")))
print(f"{len(blind)} rows; {len(blind) - len(dis)} agree; {len(dis)} disagree")
for d in dis:
    print(f"  blind #{d[0]} {d[1]}: Kevin={d[2]}, original={d[3]} | Kevin: {d[4]} | original: {d[5]}")
print("OUTCOME:", "number stands" if not dis else "discuss and resolve" if len(dis) == 1
      else "RE-ADJUDICATE the full sample by someone other than the resolver's author")
