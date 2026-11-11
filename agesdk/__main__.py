"""Command line: python -m agesdk <command>"""
from __future__ import annotations

import argparse
import json
import sys

from agesdk import db, fixture, reference
from agesdk.sources import drugage


def cmd_init_db(conn, args):
    db.init_db(conn)
    n = reference.load_species(conn)
    print(f"schema v{db.SCHEMA_VERSION} ready at {db.db_path()}; {n} species tiers loaded")


def cmd_fetch_drugage(conn, args):
    out = drugage.fetch(conn, refresh=args.refresh)
    if "skipped" in out:
        print(out["skipped"])
        return
    for member in (drugage.RELEASE_MEMBER, drugage.CSV_MEMBER):
        s = out[member]
        print(f"{member}: raw_response id={s.id} {'inserted' if s.inserted else 'unchanged'}")
    print(json.dumps(out["_summary"], indent=2))


def cmd_fixture_check(conn, args):
    fx = fixture.load()
    problems = fixture.validate(fx)
    print(f"internal: {len(problems)} problem(s)")
    try:
        raw_id, rows = drugage.current_raw(conn)
        p = fixture.check_against_drugage(fx, raw_id, rows)
        print(f"vs DrugAge: {len(p)} problem(s)")
        problems += p
    except LookupError as e:
        print(f"vs DrugAge: skipped ({e})")
    if args.pubchem:
        p = fixture.check_against_pubchem(fx, conn)
        print(f"vs PubChem: {len(p)} problem(s)")
        problems += p
    for p in problems:
        print("  -", p)
    unreviewed = [c["key"] for c in fx["compounds"] if not c["review"].get("reviewed_by")]
    print(f"{len(fx['compounds'])} entries; {len(unreviewed)} awaiting human review")
    sys.exit(1 if problems else 0)


def cmd_reprogramming_check(conn, args):
    spec = reference.load_reprogramming_spec()
    problems = reference.validate_reprogramming(spec)
    print(f"file: {len(problems)} problem(s)")
    raw_id, rows = drugage.current_raw(conn)
    p = reference.check_reprogramming_vs_drugage(spec, rows)
    print(f"vs DrugAge: {len(p)} problem(s)")
    problems += p
    if not problems:
        # Load into a scratch database alongside the DrugAge rows they link to, so the
        # schema's no-bare-names rules and the dossier view are exercised for real.
        mem = fixture.build_seed_db({"compounds": [
            {"canonical_name": c["canonical_name"], "inchikey": c["inchikey"], "drugage_names": c["drugage_names"]}
            for c in spec["compounds"] if c["drugage_names"]]}, raw_id, rows)
        report = reference.load_reprogramming(mem, spec)
        print(json.dumps(report, indent=2))
        for r in mem.execute("SELECT canonical_name, evidence_tier, n_cocktails, citations, n_systemic_trials "
                             "FROM v_mechanistic_human_dossier ORDER BY canonical_name"):
            print("  dossier:", dict(r))
        bad = [dict(r) for r in mem.execute("SELECT * FROM v_entry_route_check")]
        if bad:
            problems += [f"entry route check: {b}" for b in bad]
    for p in problems:
        print("  -", p)
    sys.exit(1 if problems else 0)


def cmd_fixture_chembl(conn, args):
    print(json.dumps(fixture.chembl_report(fixture.load(), conn), indent=2))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agesdk")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db", help="create/refresh schema and load reference data")
    p = sub.add_parser("fetch-drugage", help="download DrugAge into the raw layer")
    p.add_argument("--refresh", action="store_true", help="re-download even if present")
    p = sub.add_parser("fixture-check", help="validate the seed fixture")
    p.add_argument("--pubchem", action="store_true", help="also verify CIDs/InChIKeys via PubChem")
    sub.add_parser("fixture-chembl", help="report ChEMBL IDs + ATC codes for fixture entries")
    sub.add_parser("reprogramming-check", help="validate data/reference/reprogramming_evidence.yaml")
    args = ap.parse_args(argv)

    conn = db.connect()
    db.init_db(conn)
    {"init-db": cmd_init_db, "fetch-drugage": cmd_fetch_drugage,
     "fixture-check": cmd_fixture_check, "fixture-chembl": cmd_fixture_chembl,
     "reprogramming-check": cmd_reprogramming_check}[args.cmd](conn, args)


if __name__ == "__main__":
    main()
