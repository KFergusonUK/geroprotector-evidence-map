import json
from collections import defaultdict
import sqlite3
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

from agesdk import litscan, normalise, refresh
from agesdk.sources import ctgov, drugage
from tests.test_drugage import HEADER, ROW, make_zip
from tests.test_schema import (add_compound, add_evidence, fresh, key_of, review_direction,
                               review_harm)


class FakeHTTP:
    """Routes GETs by URL. Handlers return (status, body) where body is bytes or JSON-able."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        for prefix, handler in self.routes.items():
            if url.startswith(prefix):
                status, body = handler(url, params or {})
                if not isinstance(body, bytes):
                    body = json.dumps(body).encode()
                return status, body, {}
        raise AssertionError(f"unexpected GET {url}")


def zip_client(zip_bytes):
    return FakeHTTP({drugage.URL: lambda u, p: (200, zip_bytes)})


ROW2 = "Acarbose,Mus musculus,UM-HET3,1000 ppm food,,,22,S,,NA,Male,,NA,Yes,24245565"


class DrugAgeRefresh(unittest.TestCase):
    def setUp(self):
        self.conn = fresh()

    def log(self):
        return [r["outcome"] for r in self.conn.execute("SELECT outcome FROM fetch_log ORDER BY id")]

    def raw_count(self):
        return self.conn.execute("SELECT count(*) FROM raw_response WHERE source = 'drugage'").fetchone()[0]

    def test_unchanged_archive_is_logged_not_restored(self):
        z = make_zip(f"{HEADER}\n{ROW}\n")
        self.assertTrue(drugage.refresh(self.conn, client=zip_client(z))["changed"])
        self.assertFalse(drugage.refresh(self.conn, client=zip_client(z))["changed"])
        self.assertEqual(self.log(), ["changed", "unchanged"])
        self.assertEqual(self.raw_count(), 2)          # csv + release, stored once

    def test_changed_archive_appends(self):
        drugage.refresh(self.conn, client=zip_client(make_zip(f"{HEADER}\n{ROW}\n")))
        out = drugage.refresh(self.conn, client=zip_client(make_zip(f"{HEADER}\n{ROW}\n{ROW2}\n")))
        self.assertTrue(out["changed"])
        self.assertEqual(self.raw_count(), 3)          # new csv appended; release unchanged
        self.assertEqual(len(drugage.current_rows(self.conn)), 2)

    def test_fetch_log_is_append_only(self):
        drugage.refresh(self.conn, client=zip_client(make_zip(f"{HEADER}\n{ROW}\n")))
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE fetch_log SET outcome = 'error'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM fetch_log")


class Reprocess(unittest.TestCase):
    def setUp(self):
        c = self.conn = fresh()
        self.rapa = add_compound(c, "sirolimus")
        c.execute("INSERT INTO compound_synonym VALUES (?, 'Rapamycin', 'drugage')", (self.rapa,))

    def load(self, csv_text):
        drugage.refresh(self.conn, client=zip_client(make_zip(csv_text)))
        raw_id, rows = drugage.current_raw(self.conn)
        return normalise.reprocess_drugage(self.conn, raw_id, rows)

    def test_replaces_superseded_rows(self):
        self.assertEqual(self.load(f"{HEADER}\n{ROW}\n"), {"removed": 0, "inserted": 1})
        self.assertEqual(self.load(f"{HEADER}\n{ROW}\n{ROW}\n"), {"removed": 1, "inserted": 2})

    def test_review_survives_unchanged_row_but_is_orphaned_when_source_changes(self):
        self.load(f"{HEADER}\n{ROW}\n")
        key = self.conn.execute("SELECT evidence_key FROM animal_evidence").fetchone()[0]
        review_direction(self.conn, key, "null", reason="source_error", citation="PMID:1")
        self.load(f"{HEADER}\n{ROW}\n{ROW2}\n")            # row unchanged: review still applies
        self.assertEqual(list(self.conn.execute("SELECT * FROM v_orphaned_reviews")), [])
        self.load(f"{HEADER}\n{ROW.replace(',13,', ',12,')}\n")   # the source corrected the row
        orphans = [dict(r) for r in self.conn.execute("SELECT * FROM v_orphaned_reviews")]
        self.assertEqual([(o["review_table"], o["review_key"]) for o in orphans], [("direction_review", key)])


class Transitions(unittest.TestCase):
    """Class-4 changes surface; churn is logged; first run is a baseline."""

    def setUp(self):
        c = self.conn = fresh()
        self.aca = add_compound(c, "acarbose")
        for sex in ("M", "F"):
            for pmid in ("1", "2"):
                add_evidence(c, self.aca, "extension", sex=sex, itp=1, pmid=pmid)
        self.met = add_compound(c, "metformin")
        add_evidence(c, self.met, "extension")
        self.rofe = add_compound(c, "rofecoxib")
        self.rofe_short = add_evidence(c, self.rofe, "shortening")
        review_harm(c, self.rofe)
        self.lev = add_compound(c, "levodopa")
        self.lev_row = add_evidence(c, self.lev, "conflict", avg_direction="null", max_direction="shortening")
        review_direction(c, key_of(c, self.lev_row), "null")
        c.commit()
        self.run1 = self.snap()

    def snap(self):
        run_id = refresh.start_run(self.conn)
        refresh.snapshot(self.conn, run_id, ["Acarbose", "Metformin"])
        refresh.finish_run(self.conn, run_id, {"test": "x"})
        return run_id

    def kinds(self, run_id):
        return sorted((t["transition"], t["canonical_name"] or t["subject"]) for t in refresh.transitions(self.conn, run_id))

    def add_trial(self, nct, compound, state="ONGOING", ageing=False):
        self.conn.execute("INSERT INTO trial (nct_id, results_state) VALUES (?, ?)", (nct, state))
        self.conn.execute("INSERT INTO trial_intervention (nct_id, raw_name, compound_id, systemic_exposure, "
                          "route_rule_version) VALUES (?, 'x', ?, 'systemic', 'r1')", (nct, compound))
        if ageing:
            self.conn.execute("INSERT INTO trial_outcome (nct_id, outcome_type, measure, ageing_adjacent) "
                              "VALUES (?, 'primary', 'all-cause mortality', 1)", (nct,))

    def test_baseline_has_no_transitions(self):
        self.assertEqual(refresh.transitions(self.conn, self.run1), [])
        cells = {r[0] for r in self.conn.execute("SELECT DISTINCT cell FROM snapshot_membership")}
        self.assertTrue({"untested_candidate", "under_tested", "itp_tier", "harm_candidate",
                         "harm_signal", "drugage_compound"} <= cells)

    def test_no_change_no_transitions(self):
        self.assertEqual(refresh.transitions(self.conn, self.snap()), [])

    def test_gold_cell_and_under_tested(self):
        self.add_trial("NCT1", self.aca, ageing=True)
        self.assertEqual(self.kinds(self.snap()),
                         [("entered_gold_cell", "acarbose"), ("left_under_tested", "acarbose")])

    def test_new_harm_candidate(self):
        add_evidence(self.conn, self.met, "shortening", species="Rattus norvegicus")
        self.assertEqual(self.kinds(self.snap()), [("new_harm_candidate", "metformin")])

    def test_results_now_overdue_but_trial_churn_not_surfaced(self):
        self.add_trial("NCT2", self.met, state="ONGOING")
        run2 = self.snap()
        self.assertEqual(self.kinds(run2), [])          # gaining a trial is churn (class 2)
        self.conn.execute("UPDATE trial SET results_state = 'NOT_POSTED_DUE' WHERE nct_id = 'NCT2'")
        run3 = self.snap()
        self.assertEqual(self.kinds(run3), [("results_now_overdue", "metformin")])
        churn = refresh.churn_counts(self.conn, run3)
        self.assertEqual(churn, {"trial_state:state_changed": 1})

    def test_itp_tier_changed(self):
        for sex in ("M", "F"):
            add_evidence(self.conn, self.met, "null", sex=sex, itp=1, pmid="9")
        add_evidence(self.conn, self.met, "extension", sex="M", itp=1, pmid="8")
        t = refresh.transitions(self.conn, self.snap())
        self.assertEqual([(x["transition"], x["canonical_name"], x["old_state"], x["new_state"]) for x in t],
                         [("itp_tier_changed", "metformin", None, "weak")])   # 1/3 cohorts

    def test_guard_harm_signal_never_changes_without_a_human(self):
        # New evidence arrives: the reviewed decision is flagged, not updated.
        add_evidence(self.conn, self.rofe, "shortening", species="Rattus norvegicus")
        run2 = self.snap()
        self.assertEqual(self.kinds(run2), [("harm_review_needs_revisit", "rofecoxib")])
        still = {r[0] for r in self.conn.execute("SELECT canonical_name FROM v_harm_signal")}
        self.assertEqual(still, {"rofecoxib"})
        # Evidence withdrawn: still in v_harm_signal until a human acts.
        self.conn.execute("UPDATE animal_evidence SET direction = 'null' WHERE compound_id = ?", (self.rofe,))
        self.snap()
        self.assertEqual({r[0] for r in self.conn.execute("SELECT canonical_name FROM v_harm_signal")}, {"rofecoxib"})
        harm_signal_changes = [r for r in self.conn.execute(
            "SELECT * FROM v_membership_changes WHERE cell = 'harm_signal'")]
        self.assertEqual(harm_signal_changes, [])

    def test_orphaned_review_surfaces(self):
        self.conn.execute("DELETE FROM animal_evidence WHERE id = ?", (self.lev_row,))
        self.assertIn(("review_orphaned", f"direction_review:{key_of_deleted(self)}"), self.kinds(self.snap()))

    def test_snapshot_history_is_immutable(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE snapshot_membership SET state = 'x'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM snapshot_membership")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE snapshot_run SET note = 'rewritten' WHERE run_id = ?", (self.run1,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM snapshot_run")

    def test_failed_run_is_skipped_in_comparison(self):
        bad = refresh.start_run(self.conn)
        refresh.finish_run(self.conn, bad, {}, status="failed")
        add_evidence(self.conn, self.met, "shortening", species="Rattus norvegicus")
        run3 = self.snap()
        t = refresh.transitions(self.conn, run3)
        self.assertEqual({x["prev_run_id"] for x in t}, {self.run1})

    def test_entered_cell_is_auditable(self):
        self.add_trial("NCT1", self.aca, ageing=True)
        self.snap()
        r = dict(self.conn.execute("SELECT * FROM v_membership_changes WHERE cell = 'gold_cell'").fetchone())
        ev = json.loads(r["new_evidence"])
        self.assertEqual((ev["itp_cohorts"], ev["itp_tier"], ev["systemic_trials"]), ("4/4", "strong", 1))
        self.assertIsNotNone(r["finished_at"])


def key_of_deleted(t):
    return t.conn.execute("SELECT evidence_key FROM direction_review").fetchone()[0]


def ctgov_routes(pages_by_since=None):
    """Empty registry: §11 refresh with no query plan makes only the version call."""
    from tests.test_ctgov import FakeRegistry
    reg = FakeRegistry({}, {})
    return FakeHTTP({f"{ctgov.BASE}/version": lambda u, p: reg.get(u, p)[:2],
                     f"{ctgov.BASE}/studies": lambda u, p: reg.get(u, p)[:2]})


class CtgovRefreshErrors(unittest.TestCase):
    def test_error_does_not_advance_watermark(self):
        from agesdk.raw import last_watermark
        from tests.test_ctgov import FX, registry
        conn = fresh()
        ctgov.fetch_seed(conn, FX, client=registry())
        broken = FakeHTTP({f"{ctgov.BASE}/version": lambda u, p: (200, {"apiVersion": "2", "dataTimestamp": "2026-11-17T00:00:00"}),
                           f"{ctgov.BASE}/studies": lambda u, p: (503, b"down")})
        with self.assertRaises(Exception):
            ctgov.refresh(conn, ["metformin"], client=broken)
        self.assertEqual(last_watermark(conn, "ctgov", "studies", {"query.intr": "metformin"}), "2026-11-10")


def litscan_client(hits, chems):
    def search(url, params):
        if params.get("cursorMark") != "*":
            return 200, {"resultList": {"result": []}}
        return 200, {"hitCount": len(hits), "nextCursorMark": "end", "resultList": {"result": hits}}

    def annotations(url, params):
        ids = [i.split(":")[1] for i in params["articleIds"].split(",")]
        return 200, [{"extId": i, "annotations": [{"exact": c} for c in chems.get(i, [])]} for i in ids]
    return FakeHTTP({f"{litscan.SEARCH_BASE}/search": search,
                     f"{litscan.ANNOT_BASE}/annotationsByArticleIds": annotations})


class LiteratureScan(unittest.TestCase):
    HITS = [{"pmid": "1", "title": "Obtusifolin extends lifespan in C. elegans"},
            {"pmid": "2", "title": "Rapamycin extends lifespan again"},
            {"pmid": "3", "title": "Reagents only"}]
    CHEMS = {"1": ["obtusifolin", "Obtusifolin", "DMSO"], "2": ["rapamycin"], "3": ["paraformaldehyde", "Triton"]}

    def setUp(self):
        self.conn = fresh()
        rapa = add_compound(self.conn, "sirolimus")
        self.conn.execute("INSERT INTO compound_synonym VALUES (?, 'rapamycin', 'fixture')", (rapa,))

    def scan(self, **kw):
        return litscan.scan(self.conn, today=date(2026, 11, 11),
                            client=litscan_client(self.HITS, self.CHEMS), **kw)

    def test_queues_only_unknown_non_reagent_chemicals(self):
        out = self.scan()
        self.assertEqual((out["hits"], out["queued"], out["only_known_chemicals"]), (3, 1, 2))
        row = dict(self.conn.execute("SELECT * FROM literature_candidate").fetchone())
        self.assertEqual((row["pmid"], row["status"], json.loads(row["unmatched_chemicals"])),
                         ("1", "queued", ["obtusifolin"]))

    def test_never_writes_outside_the_queue(self):
        writes = []
        self.conn.set_trace_callback(lambda sql: writes.append(sql))
        before = self.conn.execute("SELECT count(*) FROM compound").fetchone()[0]
        self.scan()
        self.conn.set_trace_callback(None)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM compound").fetchone()[0], before)
        forbidden = ("compound", "crosswalk", "animal_evidence", "harm_review", "direction_review",
                     "compound_synonym", "reprogramming_evidence")
        for sql in writes:
            s = " ".join(sql.split()).lower()
            if s.startswith(("insert", "update", "delete")):
                target = s.split()[2] if s.startswith("insert") else s.split()[1]
                if s.startswith("insert or ignore"):
                    target = s.split()[4]
                self.assertNotIn(target, forbidden, sql)

    def test_queue_status_needs_a_named_human(self):
        self.scan()
        for reviewer in (None, "auto"):
            with self.assertRaises(sqlite3.IntegrityError, msg=reviewer):
                self.conn.execute("UPDATE literature_candidate SET status = 'relevant_needs_curation', "
                                  "reviewed_by = ?, reviewed_at = '2026-11-12'", (reviewer,))

    def test_weekly_window_follows_watermark(self):
        first = self.scan()
        self.assertEqual((first["from"], first["to"]), ("2026-11-04", "2026-11-11"))
        nxt = litscan.scan(self.conn, today=date(2026, 11, 18), client=litscan_client([], {}))
        self.assertEqual((nxt["from"], nxt["to"]), ("2026-11-11", "2026-11-18"))

    def test_rules_file_is_versioned(self):
        rules = litscan.load_rules()
        self.assertTrue(rules["version"].startswith("litscan-v"))
        self.assertIn("{from}", rules["query"])


class EndToEnd(unittest.TestCase):
    def client(self, zip_bytes):
        routes = {drugage.URL: lambda u, p: (200, zip_bytes)}
        routes.update(ctgov_routes().routes)
        routes.update(litscan_client([], {}).routes)
        return FakeHTTP(routes)

    def test_changelog_only_when_transitions(self):
        conn = fresh()
        rapa = add_compound(conn, "sirolimus")
        conn.execute("INSERT INTO compound_synonym VALUES (?, 'Rapamycin', 'drugage')", (rapa,))
        m = add_compound(conn, "CHIR-99021", "reprogramming_cocktail")
        conn.commit()
        with TemporaryDirectory() as d:
            out = Path(d)
            c = self.client(make_zip(f"{HEADER}\n{ROW}\n"))
            kw = dict(changelog_dir=out, today=date(2026, 11, 11),
                      clients={"drugage": c, "ctgov": c, "litscan": c})
            r1 = refresh.run(conn, **kw)
            self.assertEqual((r1.transitions, r1.changelog_path), ([], None))
            r2 = refresh.run(conn, **kw)
            self.assertIsNone(r2.changelog_path)
            self.assertEqual(list(out.iterdir()), [])
            # New DrugAge build with a mammal shortening row for rapamycin: a harm candidate.
            short = ROW.replace(",13,S,", ",-12,S,").replace(",Yes,", ",No,")
            c = self.client(make_zip(f"{HEADER}\n{ROW}\n{short}\n"))
            kw["clients"] = {"drugage": c, "ctgov": c, "litscan": c}
            r3 = refresh.run(conn, **kw)
            self.assertEqual([t["transition"] for t in r3.transitions], ["new_harm_candidate"])
            text = r3.changelog_path.read_text()
            self.assertIn("New harm candidate (needs human review)", text)
            self.assertIn("sirolimus", text)
            self.assertIn("measured lifespan", text)
            self.assertEqual(r3.churn, {})


if __name__ == "__main__":
    unittest.main()
