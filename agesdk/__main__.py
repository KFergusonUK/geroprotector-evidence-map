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
        rows = drugage.current_rows(conn)
        p = fixture.check_against_drugage(fx, rows, fixture.load_species_tiers())
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
    args = ap.parse_args(argv)

    conn = db.connect()
    db.init_db(conn)
    {"init-db": cmd_init_db, "fetch-drugage": cmd_fetch_drugage,
     "fixture-check": cmd_fixture_check, "fixture-chembl": cmd_fixture_chembl}[args.cmd](conn, args)


if __name__ == "__main__":
    main()
