"""Build a blind-check packet for a step-4 precision sample.

30 of the 200 sampled rows, chosen by a fixed seed, with the registry record as registered
and none of the original adjudicator's verdicts. Usage:
    python3 docs/step4_blind_packet.py 4  > docs/step4_blind_check.yaml
    python3 docs/step4_blind_packet.py 4b > docs/step4b_blind_check.yaml
"""
import json
import random
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agesdk import db  # noqa: E402

ROUNDS = {"4": ("step4_sample.py", 2026111830, "2050f70"), "4b": ("step4b_sample.py", 2026111930, "SEE_GIT_LOG")}
ROUND = sys.argv[1] if len(sys.argv) > 1 else "4"
SAMPLER, BLIND_SEED, VERDICT_COMMIT = ROUNDS[ROUND]
K = 30
sample = json.loads(subprocess.run([sys.executable, str(Path(__file__).with_name(SAMPLER))],
                                   capture_output=True, text=True, check=True).stdout)
picks = sorted(random.Random(BLIND_SEED).sample(range(len(sample)), K))
conn = db.connect()
rows = []
for b, i in enumerate(picks, start=1):
    r = sample[i]
    iv = json.loads(conn.execute("SELECT object_json FROM ctgov_intervention WHERE nct_id = ? AND idx = ?",
                                 (r["nct_id"], r["idx"])).fetchone()[0])
    title, arms = conn.execute("SELECT brief_title, arm_groups FROM ctgov_study WHERE nct_id = ?",
                               (r["nct_id"],)).fetchone()
    rows.append({
        "blind_id": b, "sample_index": i, "nct_id": r["nct_id"],
        "registry_url": f"https://clinicaltrials.gov/study/{r['nct_id']}",
        "claim": f"This intervention object is {r['compound_key']}",
        "intervention": {k: iv.get(k) for k in ("type", "name", "otherNames", "description", "armGroupLabels")},
        "study_title": title,
        "arm_groups": [{k: a.get(k) for k in ("label", "type", "description")} for a in json.loads(arms or "[]")],
        "verdict": None,      # fill in: correct | incorrect
        "note": "",
    })
header = """# Blind check of the step-4 precision sample — for Kevin Ferguson to adjudicate.
#
# Judge each claim ("This intervention object is <compound>") by the protocol's identity rule
# (docs/step4_precision_protocol.md, "Adjudication"):
#   CORRECT   the intervention administers the compound itself: any salt, hydrate,
#             formulation, brand or sponsor code of that molecule (lithium salts -> Li+).
#   INCORRECT a different molecule (incl. stereoisomers, analogues), a placebo or dummy, a
#             fixed-dose combination presented as a single agent, an extract or food, or a
#             class or regimen rather than the compound.
#   Ambiguous counts as INCORRECT. Route is NOT part of identity (a sirolimus stent is sirolimus).
#
# Set `verdict` to correct or incorrect, optionally a `note`. Please do not open the
# original verdicts (data/reviews/step4*_precision_sample.yaml) until you have finished.
# Then run: python3 docs/step4_blind_compare.py ROUND
"""
sys.stdout.write(header + f"# Round {ROUND}: 30 of 200, random.Random({BLIND_SEED}); original verdicts "
                 f"committed before this packet was generated.\n")
yaml.safe_dump({"rows": rows}, sys.stdout, sort_keys=False, allow_unicode=True, width=110)
