"""Blind check for the estriol census (docs/estriol_census_protocol.md, step 5).

N = 18 <= 30, so the packet holds every row, shuffled by random.Random(20261125), with the
registry record as registered and none of Claude's verdicts (committed in 46e4f39 before
this packet was generated).

    python3 docs/estriol_blind.py packet  > docs/estriol_blind_check.yaml
    python3 docs/estriol_blind.py compare      # after Kevin has filled in every verdict
"""
import csv
import json
import random
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agesdk import db  # noqa: E402

SEED = 20261125
PACKET = ROOT / "docs" / "estriol_blind_check.yaml"
VERDICTS = ROOT / "data" / "reviews" / "estriol_census.yaml"
HEADER = """# Blind check of the estriol census, for Kevin Ferguson (docs/estriol_census_protocol.md).
#
# Judge each claim ("This intervention object is estriol") by the identity rule in
# docs/step4_precision_protocol.md:
#   correct    the intervention administers estriol itself (any formulation, brand, dose).
#   incorrect  a different molecule (estradiol, estrone, 16-epiestriol...), a placebo, an ester
#              prodrug (e.g. estriol succinate) or a combination product presented as estriol.
#   Ambiguous counts as incorrect. Route is NOT part of identity (a vaginal gel is estriol).
#
# Set `verdict` to correct or incorrect and add a `note` where useful. Please do not open
# data/reviews/estriol_census.yaml until you have finished. Then run:
#     python3 docs/estriol_blind.py compare
"""


def packet() -> None:
    pop = list(csv.DictReader(open(ROOT / "data" / "measurements" / "estriol_population.csv")))
    order = list(range(len(pop)))
    random.Random(SEED).shuffle(order)
    conn = db.connect()
    rows = []
    for b, j in enumerate(order, start=1):
        p = pop[j]
        iv = json.loads(conn.execute("SELECT object_json FROM ctgov_intervention WHERE nct_id = ? AND idx = ?",
                                     (p["nct_id"], int(p["idx"]))).fetchone()[0])
        title, arms = conn.execute("SELECT brief_title, arm_groups FROM ctgov_study WHERE nct_id = ?",
                                   (p["nct_id"],)).fetchone()
        rows.append({
            "blind_id": b, "census_i": j + 1, "nct_id": p["nct_id"],
            "registry_url": f"https://clinicaltrials.gov/study/{p['nct_id']}",
            "claim": "This intervention object is estriol",
            "intervention": {k: iv.get(k) for k in ("type", "name", "otherNames", "description", "armGroupLabels")},
            "study_title": title,
            "arm_groups": [{k: a.get(k) for k in ("label", "type", "description")} for a in json.loads(arms or "[]")],
            "verdict": None,
            "note": "",
        })
    sys.stdout.write(HEADER)
    yaml.safe_dump({"rows": rows}, sys.stdout, sort_keys=False, allow_unicode=True, width=110)


def compare() -> None:
    blind = yaml.safe_load(open(PACKET, encoding="utf-8"))["rows"]
    orig = {r["i"]: r for r in yaml.safe_load(open(VERDICTS, encoding="utf-8"))["rows"]}
    missing = [b["blind_id"] for b in blind if str(b["verdict"]).lower() not in ("correct", "incorrect")]
    if missing:
        sys.exit(f"verdict missing or not 'correct'/'incorrect' for blind_id {missing}")
    dis = [b for b in blind if (str(b["verdict"]).lower() == "correct") != orig[b["census_i"]]["identity_correct"]]
    print(f"{len(blind)} rows; {len(blind) - len(dis)} agree; {len(dis)} disagree")
    for b in dis:
        o = orig[b["census_i"]]
        print(f"  blind #{b['blind_id']} {b['nct_id']}: Kevin={b['verdict']}, Claude="
              f"{'correct' if o['identity_correct'] else 'incorrect'} | Kevin: {b.get('note', '')} | Claude: {o['note']}")
    print("OUTCOME:", "number stands" if not dis else "discuss and resolve" if len(dis) == 1
          else "RE-ADJUDICATE the census by someone other than the resolver's author")


if __name__ == "__main__":
    {"packet": packet, "compare": compare}[sys.argv[1] if len(sys.argv) > 1 else "packet"]()
