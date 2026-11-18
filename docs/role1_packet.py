"""Build the role-1 labelling packet: the registry record as registered, no resolver output.
Usage: python3 docs/role1_packet.py > docs/role1_packet.yaml"""
import json
import subprocess
import sys
from pathlib import Path

import yaml

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from agesdk import db  # noqa: E402
from agesdk.sources import ctgov  # noqa: E402

sample = json.loads(subprocess.run([sys.executable, str(root / "docs" / "role1_sample.py")],
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
sys.stdout.write("""# Role-1 labelling packet (docs/role1_protocol.md). For BOTH readers, independently.
# Copy this file to data/reviews/role1_labels_<you>.yaml, set each `label` to one of
#   experimental | comparator | background | unclear
# following the protocol's labelling rules, add a `note` where useful, and COMMIT your file
# before looking at the other reader's. Do not open data/measurements/role1_resolver_roles.csv.
""")
yaml.safe_dump({"rows": rows}, sys.stdout, sort_keys=False, allow_unicode=True, width=110)
