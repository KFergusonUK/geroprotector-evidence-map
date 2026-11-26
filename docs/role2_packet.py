"""Build the role-2 labelling packet (docs/role2_protocol.md): the registry record as registered, no resolver output.
Usage: python3 docs/role2_packet.py > docs/role2_packet.yaml"""
import json
import subprocess
import sys
from pathlib import Path

import yaml

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from agesdk import db  # noqa: E402
from agesdk.sources import ctgov  # noqa: E402

sample = json.loads(subprocess.run([sys.executable, str(root / "docs" / "role2_sample.py")],
                                   capture_output=True, text=True, check=True).stdout)
conn = db.connect()
rows = []
for k, (nct, idx, compound) in enumerate(sample, start=1):
    rec = ctgov.study_record(conn, nct)["protocolSection"]
    ivs = rec.get("armsInterventionsModule", {}).get("interventions", [])
    rows.append({
        "id": k, "nct_id": nct, "registry_url": f"https://clinicaltrials.gov/study/{nct}",
        "question": f"Role of {compound} in this trial (the intervention object below names it)",
        "compound": compound, "intervention_index": idx,
        "intervention": {f: ivs[idx].get(f) for f in ("type", "name", "otherNames", "description", "armGroupLabels")},
        "all_interventions": [iv.get("name") for iv in ivs],
        "arm_groups": [{f: a.get(f) for f in ("label", "type", "description", "interventionNames")}
                       for a in rec.get("armsInterventionsModule", {}).get("armGroups", [])],
        "study_type": rec.get("designModule", {}).get("studyType"),
        "title": rec["identificationModule"].get("officialTitle") or rec["identificationModule"].get("briefTitle"),
        "summary": (rec.get("descriptionModule", {}).get("briefSummary") or "")[:1200],
        "label": None,       # experimental | comparator | background | unclear
        "note": "",
    })
sys.stdout.write("""# Role-2 labelling packet (docs/role2_protocol.md). Rules: docs/role2_rules.md (v2): read them first.
# Copy this file to data/reviews/role2_labels_<you>.yaml. For each row set `label` to one of
#   experimental | comparator | background | unclear
# and a `note` naming the question that decided it, e.g. "Q1: same 1000 mg in both arms".
# The five questions, in order (full wording and examples in docs/role2_rules.md):
#   Q1 Same dose and form in every arm, its use not compared?                     -> background
#   Q2 Record calls it a probe/challenge, or supporting care for something else?  -> background
#   Q3 Record calls it the control/reference/standard/usual treatment?            -> comparator
#   Q4 Record evaluates its effect, presence vs absence, or its dose/schedule/form? -> experimental
#   Q5 Still uncertain or contradictory?                                          -> unclear
# Label in order, do not skip; stopping early is fine. COMMIT your file before any comparison.
# Do not open data/measurements/role2_resolver_roles.csv or another reader's labels.
""")
yaml.safe_dump({"rows": rows}, sys.stdout, sort_keys=False, allow_unicode=True, width=110)
