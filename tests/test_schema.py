import sqlite3
import unittest

from agesdk import db


def fresh():
    conn = db.connect(":memory:")
    db.init_db(conn)
    return conn


def add_compound(conn, name, route, inchikey=None):
    cur = conn.execute("INSERT INTO compound (canonical_name, entry_route, inchikey) VALUES (?, ?, ?)",
                       (name, route, inchikey))
    return cur.lastrowid


def add_atc(conn, cid, code, status="auto", reviewer=None):
    conn.execute("INSERT INTO compound_atc (compound_id, atc_code, review_status, reviewed_by) "
                 "VALUES (?, ?, ?, ?)", (cid, code, status, reviewer))


def add_evidence(conn, cid, species="Mus musculus"):
    conn.execute("INSERT INTO animal_evidence (compound_id, species, source_compound_name) "
                 "VALUES (?, ?, 'x')", (cid, species))


class SchemaConstraints(unittest.TestCase):
    def setUp(self):
        self.conn = fresh()

    def test_init_is_idempotent(self):
        db.init_db(self.conn)
        db.init_db(self.conn)
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], db.SCHEMA_VERSION)

    def test_entry_route_enum(self):
        with self.assertRaises(sqlite3.IntegrityError):
            add_compound(self.conn, "x", "inferred")

    def test_truncated_inchikey_rejected(self):
        # First block only: would merge 17-alpha and 17-beta estradiol.
        with self.assertRaises(sqlite3.IntegrityError):
            add_compound(self.conn, "17a", "direct", "VOXZDWNPVJITMN")

    def test_stereoisomers_coexist(self):
        add_compound(self.conn, "17-alpha-estradiol", "direct", "VOXZDWNPVJITMN-SFFUCWETSA-N")
        add_compound(self.conn, "estradiol", "class", "VOXZDWNPVJITMN-ZBRFXRBCSA-N")

    def test_fuzzy_crosswalk_requires_reviewer(self):
        cid = add_compound(self.conn, "x", "direct")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO crosswalk (from_source, from_value, compound_id, method, confidence) "
                              "VALUES ('ctgov', 'rapamune 2mg', ?, 'fuzzy', 0.8)", (cid,))
        self.conn.execute("INSERT INTO crosswalk (from_source, from_value, compound_id, method, confidence, "
                          "reviewed_by) VALUES ('ctgov', 'rapamune 2mg', ?, 'fuzzy', 0.8, 'kf')", (cid,))

    def test_results_state_enum(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO trial (nct_id, results_state) VALUES ('NCT0', 'YES')")
        self.conn.execute("INSERT INTO trial (nct_id, results_state) VALUES ('NCT0', 'NOT_POSTED_DUE')")

    def test_raw_layer_append_only(self):
        self.conn.execute("INSERT INTO raw_response (source, endpoint, request_params, response_body, "
                          "fetched_at, content_sha256) VALUES ('s', 'e', '{}', 'b', 't', 'h')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE raw_response SET response_body = 'changed'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM raw_response")

    def test_atc_code_format_and_level4(self):
        cid = add_compound(self.conn, "x", "direct")
        with self.assertRaises(sqlite3.IntegrityError):
            add_atc(self.conn, cid, "A10BK")          # level 4 is not a substance code
        add_atc(self.conn, cid, "A10BK02")
        self.assertEqual(self.conn.execute("SELECT atc_level4 FROM compound_atc").fetchone()[0], "A10BK")

    def test_accepted_atc_requires_reviewer(self):
        cid = add_compound(self.conn, "x", "direct")
        with self.assertRaises(sqlite3.IntegrityError):
            add_atc(self.conn, cid, "B01AC06", status="accepted")


class ClassEntry(unittest.TestCase):
    """SPEC §5.5: one-hop class entry through reviewed-or-unambiguous ATC level-4 classes."""

    def setUp(self):
        c = self.conn = fresh()
        self.cana = add_compound(c, "canagliflozin", "direct")
        add_evidence(c, self.cana)
        add_atc(c, self.cana, "A10BK02")
        self.empa = add_compound(c, "empagliflozin", "class")
        add_atc(c, self.empa, "A10BK03")
        self.sema = add_compound(c, "semaglutide", "class")
        add_atc(c, self.sema, "A10BJ06")

    def basis(self, cid):
        return [r["basis_canonical_name"] for r in self.conn.execute(
            "SELECT basis_canonical_name FROM v_class_entry_basis WHERE compound_id = ?", (cid,))]

    def problems(self):
        return {r["canonical_name"]: r["problem"] for r in self.conn.execute("SELECT * FROM v_entry_route_check")}

    def test_empagliflozin_enters_via_canagliflozin(self):
        self.assertEqual(self.basis(self.empa), ["canagliflozin"])
        self.assertNotIn("empagliflozin", self.problems())

    def test_semaglutide_has_no_basis(self):
        self.assertEqual(self.basis(self.sema), [])
        self.assertEqual(self.problems()["semaglutide"], "class_without_basis")

    def test_pending_review_blocks_class_entry(self):
        self.conn.execute("UPDATE compound_atc SET review_status = 'pending_review' WHERE compound_id = ?",
                          (self.cana,))
        self.assertEqual(self.basis(self.empa), [])

    def test_rejected_class_blocks_entry(self):
        self.conn.execute("UPDATE compound_atc SET review_status = 'rejected', reviewed_by = 'kf' "
                          "WHERE compound_id = ?", (self.empa,))
        self.assertEqual(self.basis(self.empa), [])

    def test_class_entry_is_one_hop(self):
        # empagliflozin (class) also in a hypothetical second class; its classmate must not enter.
        add_atc(self.conn, self.empa, "C99ZZ01")
        other = add_compound(self.conn, "classmate-of-a-class-entrant", "class")
        add_atc(self.conn, other, "C99ZZ02")
        self.assertEqual(self.basis(other), [])

    def test_basis_needs_animal_evidence(self):
        self.conn.execute("DELETE FROM animal_evidence")
        self.assertEqual(self.basis(self.empa), [])
        self.assertEqual(self.problems()["canagliflozin"], "direct_without_animal_evidence")

    def test_direct_compound_marked_class_is_flagged(self):
        add_evidence(self.conn, self.empa)
        self.assertEqual(self.problems()["empagliflozin"], "class_but_has_animal_evidence")


class AtcReviewFlags(unittest.TestCase):
    def setUp(self):
        self.conn = fresh()

    def flagged(self):
        return {(r["canonical_name"], r["atc_code"]): r["reason"]
                for r in self.conn.execute("SELECT * FROM v_atc_review_needed")}

    def test_multi_class_flagged(self):
        asp = add_compound(self.conn, "aspirin", "direct")
        add_atc(self.conn, asp, "B01AC06", status="pending_review")
        add_atc(self.conn, asp, "N02BA01", status="pending_review")
        self.assertEqual(self.flagged(), {("aspirin", "B01AC06"): "multi_class",
                                          ("aspirin", "N02BA01"): "multi_class"})

    def test_two_codes_same_level4_not_multi_class(self):
        c = add_compound(self.conn, "x", "direct")
        add_atc(self.conn, c, "A10BA02")
        add_atc(self.conn, c, "A10BA03")
        self.assertEqual(self.flagged(), {})

    def test_other_bucket_flagged(self):
        c = add_compound(self.conn, "taurine", "direct")
        add_atc(self.conn, c, "A16AA99", status="auto")
        add_atc(self.conn, c, "A16AX99", status="pending_review")
        self.assertEqual(self.flagged()[("taurine", "A16AX99")], "multi_class+other_bucket")

    def test_reviewed_rows_leave_queue(self):
        asp = add_compound(self.conn, "aspirin", "direct")
        add_atc(self.conn, asp, "B01AC06", status="accepted", reviewer="kf")
        add_atc(self.conn, asp, "N02BA01", status="rejected", reviewer="kf")
        self.assertEqual(self.flagged(), {})


if __name__ == "__main__":
    unittest.main()
