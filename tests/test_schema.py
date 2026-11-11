import json
import sqlite3
import unittest

from agesdk import db
from agesdk.reference import load_species


def fresh():
    conn = db.connect(":memory:")
    db.init_db(conn)
    load_species(conn)
    return conn


def add_compound(conn, name, route="direct", inchikey=None):
    cur = conn.execute("INSERT INTO compound (canonical_name, entry_route, inchikey) VALUES (?, ?, ?)",
                       (name, route, inchikey))
    return cur.lastrowid


def add_atc(conn, cid, code, status="auto", reviewer=None):
    conn.execute("INSERT INTO compound_atc (compound_id, atc_code, review_status, reviewed_by) "
                 "VALUES (?, ?, ?, ?)", (cid, code, status, reviewer))


def add_evidence(conn, cid, direction="extension", species="Mus musculus", sex="M", itp=0, pmid=None):
    cur = conn.execute(
        "INSERT INTO animal_evidence (compound_id, species, sex, direction, direction_basis, "
        "direction_rule_version, is_itp, pmid, source_compound_name) "
        "VALUES (?, ?, ?, ?, 'avg', 'direction-v1', ?, ?, 'x')",
        (cid, species, sex, direction, itp, pmid))
    return cur.lastrowid


def review_harm(conn, cid, decision="surface", reviewer="Kevin Ferguson", exposure="approved drug",
                rationale="credible signal", evidence_ids=None):
    if evidence_ids is None:
        evidence_ids = [r[0] for r in conn.execute(
            "SELECT id FROM animal_evidence WHERE compound_id = ? AND direction = 'shortening'", (cid,))]
    conn.execute("INSERT INTO harm_review (compound_id, decision, human_exposure_basis, rationale, "
                 "reviewed_by, reviewed_at, evidence_row_ids) VALUES (?, ?, ?, ?, ?, '2026-11-11', ?)",
                 (cid, decision, exposure, rationale, reviewer, json.dumps(evidence_ids)))


class SchemaConstraints(unittest.TestCase):
    def setUp(self):
        self.conn = fresh()

    def test_init_is_idempotent(self):
        db.init_db(self.conn)
        db.init_db(self.conn)
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], db.SCHEMA_VERSION)

    def test_upgrade_keeps_raw_layer(self):
        self.conn.execute("INSERT INTO raw_response (source, endpoint, request_params, response_body, "
                          "fetched_at, content_sha256) VALUES ('s', 'e', '{}', 'b', 't', 'h')")
        self.conn.execute("PRAGMA user_version = 1")
        db.init_db(self.conn)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM raw_response").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], db.SCHEMA_VERSION)

    def test_upgrade_refuses_to_discard_normalised_data(self):
        add_compound(self.conn, "x")
        self.conn.execute("PRAGMA user_version = 1")
        with self.assertRaises(db.MigrationError):
            db.init_db(self.conn)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM compound").fetchone()[0], 1)

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
        cid = add_compound(self.conn, "x")
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
        cid = add_compound(self.conn, "x")
        with self.assertRaises(sqlite3.IntegrityError):
            add_atc(self.conn, cid, "A10BK")          # level 4 is not a substance code
        add_atc(self.conn, cid, "A10BK02")
        self.assertEqual(self.conn.execute("SELECT atc_level4 FROM compound_atc").fetchone()[0], "A10BK")

    def test_accepted_atc_requires_reviewer(self):
        cid = add_compound(self.conn, "x")
        with self.assertRaises(sqlite3.IntegrityError):
            add_atc(self.conn, cid, "B01AC06", status="accepted")

    def test_direction_enum_and_required(self):
        cid = add_compound(self.conn, "x")
        with self.assertRaises(sqlite3.IntegrityError):
            add_evidence(self.conn, cid, direction="harmful")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO animal_evidence (compound_id, species, source_compound_name, "
                              "direction_basis, direction_rule_version) VALUES (?, 'Mus musculus', 'x', 'avg', 'v')",
                              (cid,))
        for d in ("extension", "shortening", "null", "unassessed"):
            add_evidence(self.conn, cid, direction=d)

    def test_systemic_exposure_enum_and_rule_version(self):
        self.conn.execute("INSERT INTO trial (nct_id, results_state) VALUES ('NCT1', 'ONGOING')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO trial_intervention (nct_id, raw_name, systemic_exposure, "
                              "route_rule_version) VALUES ('NCT1', 'a', 'topical', 'r1')")
        with self.assertRaises(sqlite3.IntegrityError):   # classified without a rule version
            self.conn.execute("INSERT INTO trial_intervention (nct_id, raw_name, systemic_exposure) "
                              "VALUES ('NCT1', 'b', 'local')")
        self.conn.execute("INSERT INTO trial_intervention (nct_id, raw_name, route, systemic_exposure, "
                          "route_rule_version) VALUES ('NCT1', 'sirolimus-eluting stent', 'implant', 'local', 'r1')")


class SameSubstanceLink(unittest.TestCase):
    def setUp(self):
        self.conn = fresh()
        self.ndga = add_compound(self.conn, "nordihydroguaiaretic acid", "direct", "HCZKYJDFEPMADG-UHFFFAOYSA-N")
        self.maso = add_compound(self.conn, "masoprocol", "class", "HCZKYJDFEPMADG-TXEJJXNPSA-N")

    def link(self, a, b, reviewer="Kevin Ferguson"):
        self.conn.execute("INSERT INTO compound_relation (compound_id, related_compound_id, relation, "
                          "reviewed_by, reviewed_at) VALUES (?, ?, 'same_substance_as', ?, '2026-11-11')",
                          (a, b, reviewer))

    def test_link_keeps_rows_and_keys_separate(self):
        self.link(self.ndga, self.maso)
        keys = [r[0] for r in self.conn.execute("SELECT inchikey FROM compound ORDER BY compound_id")]
        self.assertEqual(keys, ["HCZKYJDFEPMADG-UHFFFAOYSA-N", "HCZKYJDFEPMADG-TXEJJXNPSA-N"])

    def test_link_requires_reviewer(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.link(self.ndga, self.maso, reviewer=" ")

    def test_link_stored_once_in_canonical_order(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.link(self.maso, self.ndga)


class ClassEntry(unittest.TestCase):
    """SPEC §5.5: one-hop class entry through specific, reviewed-or-unambiguous ATC classes."""

    def setUp(self):
        c = self.conn = fresh()
        self.cana = add_compound(c, "canagliflozin")
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
        add_atc(self.conn, self.empa, "C99ZZ01")
        other = add_compound(self.conn, "classmate-of-a-class-entrant", "class")
        add_atc(self.conn, other, "C99ZZ02")
        self.assertEqual(self.basis(other), [])

    def test_basis_needs_animal_evidence(self):
        self.conn.execute("DELETE FROM animal_evidence")
        self.assertEqual(self.basis(self.empa), [])
        self.assertEqual(self.problems()["canagliflozin"], "direct_without_animal_evidence")

    def test_shortening_never_propagates_through_class(self):
        # A carcinogen that shortens lifespan must not pull its class-mates into the map.
        self.conn.execute("UPDATE animal_evidence SET direction = 'shortening'")
        self.assertEqual(self.basis(self.empa), [])

    def test_null_evidence_never_propagates_through_class(self):
        self.conn.execute("UPDATE animal_evidence SET direction = 'null'")
        self.assertEqual(self.basis(self.empa), [])

    def test_direct_compound_marked_class_is_flagged(self):
        add_evidence(self.conn, self.empa)
        self.assertEqual(self.problems()["empagliflozin"], "class_but_has_animal_evidence")


class ResidualAtcClasses(unittest.TestCase):
    """Residual (…X) groupings are not mechanisms and never carry class entry."""

    def setUp(self):
        self.conn = fresh()

    def test_residual_code_must_be_marked_residual(self):
        c = add_compound(self.conn, "taurine")
        for status in ("auto", "pending_review"):
            with self.assertRaises(sqlite3.IntegrityError):
                add_atc(self.conn, c, "A16AX99", status=status)
        with self.assertRaises(sqlite3.IntegrityError):
            add_atc(self.conn, c, "A16AX99", status="accepted", reviewer="kf")
        add_atc(self.conn, c, "A16AX99", status="residual")

    def test_specific_code_cannot_be_residual(self):
        c = add_compound(self.conn, "x")
        with self.assertRaises(sqlite3.IntegrityError):
            add_atc(self.conn, c, "A10BK02", status="residual")

    def test_residual_class_carries_no_entry(self):
        a = add_compound(self.conn, "direct-in-residual")
        add_evidence(self.conn, a)
        add_atc(self.conn, a, "A16AX01", status="residual")
        b = add_compound(self.conn, "classmate", "class")
        add_atc(self.conn, b, "A16AX02", status="residual")
        self.assertEqual(self.conn.execute(
            "SELECT count(*) FROM v_class_entry_basis WHERE compound_id = ?", (b,)).fetchone()[0], 0)


class AtcReviewFlags(unittest.TestCase):
    def setUp(self):
        self.conn = fresh()

    def flagged(self):
        return {(r["canonical_name"], r["atc_code"]): r["reason"]
                for r in self.conn.execute("SELECT * FROM v_atc_review_needed")}

    def test_multi_class_flagged(self):
        asp = add_compound(self.conn, "aspirin")
        add_atc(self.conn, asp, "B01AC06", status="pending_review")
        add_atc(self.conn, asp, "N02BA01", status="pending_review")
        self.assertEqual(self.flagged(), {("aspirin", "B01AC06"): "multi_class",
                                          ("aspirin", "N02BA01"): "multi_class"})

    def test_two_codes_same_level4_not_multi_class(self):
        c = add_compound(self.conn, "x")
        add_atc(self.conn, c, "A10BA02")
        add_atc(self.conn, c, "A10BA03")
        self.assertEqual(self.flagged(), {})

    def test_residual_does_not_make_a_compound_multi_class(self):
        c = add_compound(self.conn, "taurine")
        add_atc(self.conn, c, "A16AA99", status="auto")
        add_atc(self.conn, c, "A16AX99", status="residual")
        self.assertEqual(self.flagged(), {})

    def test_reviewed_rows_leave_queue(self):
        asp = add_compound(self.conn, "aspirin")
        add_atc(self.conn, asp, "B01AC06", status="accepted", reviewer="kf")
        add_atc(self.conn, asp, "N02BA01", status="rejected", reviewer="kf")
        self.assertEqual(self.flagged(), {})


class ItpRatio(unittest.TestCase):
    """SPEC §5.4: ITP evidence as cohorts positive / cohorts tested, by sex, with a documented threshold."""

    def setUp(self):
        c = self.conn = fresh()
        self.asp = add_compound(c, "aspirin")
        for sex, d in (("M", "extension"), ("M", "null"), ("M", "null"),
                       ("F", "null"), ("F", "null"), ("F", "null")):
            add_evidence(c, self.asp, direction=d, sex=sex, itp=1)
        self.met = add_compound(c, "metformin")
        add_evidence(c, self.met, direction="null", sex="M", itp=1)
        add_evidence(c, self.met, direction="null", sex="F", itp=1)
        add_evidence(c, self.met, direction="extension", species="Caenorhabditis elegans")

    def summary(self, cid):
        return dict(self.conn.execute("SELECT * FROM v_itp_summary WHERE compound_id = ?", (cid,)).fetchone())

    def test_ratio_and_sex_breakdown(self):
        s = self.summary(self.asp)
        self.assertEqual((s["itp_cohorts_positive"], s["itp_cohorts_total"]), (1, 6))
        self.assertEqual((s["itp_male_positive"], s["itp_male_total"]), (1, 3))
        self.assertEqual((s["itp_female_positive"], s["itp_female_total"]), (0, 3))

    def test_default_threshold_is_one_positive_cohort(self):
        self.assertEqual(self.summary(self.asp)["meets_itp_threshold"], 1)
        self.assertEqual(self.summary(self.met)["meets_itp_threshold"], 0)

    def test_threshold_is_data_not_code(self):
        self.conn.execute("UPDATE analysis_threshold SET value = 0.5 WHERE name = 'itp_min_positive_fraction'")
        self.assertEqual(self.summary(self.asp)["meets_itp_threshold"], 0)

    def test_null_cell_is_complement_of_threshold(self):
        nulls = {r["canonical_name"] for r in self.conn.execute("SELECT * FROM v_itp_null")}
        self.assertEqual(nulls, {"metformin"})

    def test_extension_view_carries_ratio(self):
        r = dict(self.conn.execute("SELECT * FROM v_extension_evidence WHERE compound_id = ?",
                                   (self.met,)).fetchone())
        self.assertEqual((r["itp_cohorts_positive"], r["itp_cohorts_total"]), (0, 2))
        self.assertEqual(r["has_mammal_extension"], 0)   # worm-only extension
        self.assertEqual(r["replicated"], 0)


class HarmPath(unittest.TestCase):
    """SPEC §5.7: sensitive detection, mandatory human review, never merged with extension."""

    def setUp(self):
        c = self.conn = fresh()
        self.met = add_compound(c, "metformin")
        add_evidence(c, self.met, direction="extension")
        add_evidence(c, self.met, direction="extension")
        self.met_short = add_evidence(c, self.met, direction="shortening")
        self.den = add_compound(c, "diethylnitrosamine")
        add_evidence(c, self.den, direction="shortening", species="Mesocricetus auratus")
        self.worm = add_compound(c, "worm-only-toxin")
        add_evidence(c, self.worm, direction="shortening", species="Caenorhabditis elegans")

    def signal(self):
        return {r["canonical_name"]: dict(r) for r in self.conn.execute("SELECT * FROM v_harm_signal")}

    def candidates(self):
        return {r["canonical_name"]: dict(r) for r in self.conn.execute("SELECT * FROM v_harm_candidates")}

    def test_single_mammal_signal_is_a_candidate(self):
        self.assertEqual(set(self.candidates()), {"metformin", "diethylnitrosamine"})

    def test_invertebrate_shortening_is_not_a_harm_candidate(self):
        self.assertNotIn("worm-only-toxin", self.candidates())

    def test_nothing_surfaces_without_review(self):
        self.assertEqual(self.signal(), {})
        self.assertEqual(self.candidates()["metformin"]["review_state"], "unreviewed")

    def test_review_requires_named_human(self):
        for reviewer in (None, "", "  ", "auto", "System", "pipeline"):
            with self.assertRaises(sqlite3.IntegrityError, msg=repr(reviewer)):
                review_harm(self.conn, self.met, reviewer=reviewer)

    def test_surface_requires_exposure_basis_and_rationale(self):
        with self.assertRaises(sqlite3.IntegrityError):
            review_harm(self.conn, self.met, exposure=None)
        with self.assertRaises(sqlite3.IntegrityError):
            review_harm(self.conn, self.met, rationale=" ")

    def test_reviewed_surface_appears(self):
        review_harm(self.conn, self.met)
        s = self.signal()["metformin"]
        self.assertEqual(s["reviewed_by"], "Kevin Ferguson")
        self.assertEqual(s["still_meets_threshold"], 1)
        self.assertEqual(s["evidence_changed_since_review"], 0)

    def test_rejected_does_not_appear(self):
        review_harm(self.conn, self.den, decision="reject", exposure=None, rationale="no human exposure")
        self.assertEqual(self.signal(), {})
        self.assertEqual(self.candidates()["diethylnitrosamine"]["review_state"], "reject")

    def test_new_evidence_flags_review_as_stale(self):
        review_harm(self.conn, self.met)
        add_evidence(self.conn, self.met, direction="shortening", species="Rattus norvegicus")
        self.assertEqual(self.signal()["metformin"]["evidence_changed_since_review"], 1)

    def test_withdrawn_evidence_flags_review(self):
        review_harm(self.conn, self.met)
        self.conn.execute("UPDATE animal_evidence SET direction = 'null' WHERE id = ?", (self.met_short,))
        s = self.signal()["metformin"]
        self.assertEqual(s["still_meets_threshold"], 0)
        self.assertEqual(s["evidence_changed_since_review"], 1)

    def test_paths_never_merge_counts(self):
        ext = dict(self.conn.execute("SELECT * FROM v_extension_evidence WHERE compound_id = ?",
                                     (self.met,)).fetchone())
        harm = self.candidates()["metformin"]
        self.assertEqual(ext["n_extension_rows"], 2)        # shortening row not counted
        self.assertEqual(harm["n_mammal_shortening_rows"], 1)  # extension rows not counted
        self.assertNotIn("n_mammal_shortening_rows", ext)
        self.assertNotIn("n_extension_rows", harm)

    def test_harm_only_compound_absent_from_extension_path(self):
        names = {r["canonical_name"] for r in self.conn.execute("SELECT * FROM v_extension_evidence")}
        self.assertEqual(names, {"metformin"})

    def test_harm_threshold_is_data(self):
        self.conn.execute("UPDATE analysis_threshold SET value = 2 WHERE name = 'harm_min_mammal_shortening_rows'")
        self.assertEqual(self.candidates(), {})


if __name__ == "__main__":
    unittest.main()
