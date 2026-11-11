import json
import sqlite3
import unittest

from agesdk import db
from agesdk.reference import load_species

TIER_FOR_ROUTE = {"direct": "measured_lifespan", "class": "inherited_class",
                  "reprogramming_cocktail": "mechanistic_only"}


def fresh():
    conn = db.connect(":memory:")
    db.init_db(conn)
    load_species(conn)
    return conn


def add_compound(conn, name, route="direct", inchikey=None, tier=None):
    cur = conn.execute("INSERT INTO compound (canonical_name, entry_route, evidence_tier, inchikey) "
                       "VALUES (?, ?, ?, ?)", (name, route, tier or TIER_FOR_ROUTE.get(route, "measured_lifespan"),
                                               inchikey))
    return cur.lastrowid


def add_atc(conn, cid, code, status="auto", reviewer=None):
    conn.execute("INSERT INTO compound_atc (compound_id, atc_code, review_status, reviewed_by) "
                 "VALUES (?, ?, ?, ?)", (cid, code, status, reviewer))


_seq = [0]


def add_evidence(conn, cid, direction="extension", species="Mus musculus", sex="M", itp=0, pmid=None,
                 key=None, avg_direction=None, max_direction="unassessed"):
    _seq[0] += 1
    conflict = int(direction == "conflict")
    cur = conn.execute(
        "INSERT INTO animal_evidence (compound_id, species, sex, avg_direction, max_direction, direction, "
        "direction_conflict, direction_rule_version, evidence_key, is_itp, pmid, source_compound_name) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'direction-v2', ?, ?, ?, 'x')",
        (cid, species, sex, avg_direction or ("null" if conflict else direction), max_direction,
         direction, conflict, key or f"test:{_seq[0]}", itp, pmid))
    return cur.lastrowid


def key_of(conn, evidence_id):
    return conn.execute("SELECT evidence_key FROM animal_evidence WHERE id = ?", (evidence_id,)).fetchone()[0]


def review_harm(conn, cid, decision="surface", reviewer="Kevin Ferguson", exposure="approved drug",
                rationale="credible signal", keys=None):
    if keys is None:
        keys = [r[0] for r in conn.execute(
            "SELECT evidence_key FROM animal_evidence WHERE compound_id = ? AND direction = 'shortening'", (cid,))]
    conn.execute("INSERT INTO harm_review (compound_id, decision, human_exposure_basis, rationale, "
                 "reviewed_by, reviewed_at, evidence_keys) VALUES (?, ?, ?, ?, ?, '2026-11-11', ?)",
                 (cid, decision, exposure, rationale, reviewer, json.dumps(keys)))


def review_direction(conn, key, resolved, reason="conflict_resolution", reviewer="Kevin Ferguson",
                     citation=None, rationale="checked the paper"):
    conn.execute("INSERT INTO direction_review (evidence_key, reason, resolved_direction, rationale, citation, "
                 "reviewed_by, reviewed_at) VALUES (?, ?, ?, ?, ?, ?, '2026-11-11')",
                 (key, reason, resolved, rationale, citation, reviewer))


def names(conn, view, where="1"):
    return {r["canonical_name"] for r in conn.execute(f"SELECT * FROM {view} WHERE {where}")}


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
            add_compound(self.conn, "x", "inferred", tier="measured_lifespan")

    def test_truncated_inchikey_rejected(self):
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
            add_atc(self.conn, cid, "A10BK")
        add_atc(self.conn, cid, "A10BK02")
        self.assertEqual(self.conn.execute("SELECT atc_level4 FROM compound_atc").fetchone()[0], "A10BK")

    def test_accepted_atc_requires_reviewer(self):
        cid = add_compound(self.conn, "x")
        with self.assertRaises(sqlite3.IntegrityError):
            add_atc(self.conn, cid, "B01AC06", status="accepted")

    def test_direction_enum_and_conflict_flag_consistency(self):
        cid = add_compound(self.conn, "x")
        with self.assertRaises(sqlite3.IntegrityError):
            add_evidence(self.conn, cid, direction="harmful")
        with self.assertRaises(sqlite3.IntegrityError):   # 'conflict' without the flag
            self.conn.execute("INSERT INTO animal_evidence (compound_id, species, avg_direction, max_direction, "
                              "direction, direction_conflict, direction_rule_version, evidence_key, "
                              "source_compound_name) VALUES (?, 'Mus musculus', 'null', 'shortening', "
                              "'conflict', 0, 'v', 'k', 'x')", (cid,))
        for d in ("extension", "shortening", "null", "unassessed", "conflict"):
            add_evidence(self.conn, cid, direction=d)

    def test_systemic_exposure_enum_and_rule_version(self):
        self.conn.execute("INSERT INTO trial (nct_id, results_state) VALUES ('NCT1', 'ONGOING')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO trial_intervention (nct_id, raw_name, systemic_exposure, "
                              "route_rule_version) VALUES ('NCT1', 'a', 'topical', 'r1')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO trial_intervention (nct_id, raw_name, systemic_exposure) "
                              "VALUES ('NCT1', 'b', 'local')")
        self.conn.execute("INSERT INTO trial_intervention (nct_id, raw_name, route, systemic_exposure, "
                          "route_rule_version) VALUES ('NCT1', 'sirolimus-eluting stent', 'implant', 'local', 'r1')")


class EvidenceTier(unittest.TestCase):
    """evidence_tier is the evidential grade; no view shows a compound without it."""

    def setUp(self):
        self.conn = fresh()

    def test_route_and_tier_must_agree(self):
        for route, tier in (("direct", "mechanistic_only"), ("class", "measured_lifespan"),
                            ("reprogramming_cocktail", "inherited_class")):
            with self.assertRaises(sqlite3.IntegrityError, msg=(route, tier)):
                add_compound(self.conn, f"{route}-{tier}", route, tier=tier)

    def test_every_compound_view_carries_the_tier(self):
        views = [r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type = 'view'")]
        for v in views:
            cols = {r[1] for r in self.conn.execute(f"PRAGMA table_info({v})")}
            for col in cols:
                if col.endswith("compound_id"):
                    prefix = col[: -len("compound_id")]
                    self.assertIn(f"{prefix}evidence_tier", cols, f"{v}.{col} has no tier label")

    def test_mechanistic_compound_never_on_extension_path_or_class_basis(self):
        m = add_compound(self.conn, "CHIR-99021", "reprogramming_cocktail")
        add_atc(self.conn, m, "A10BK09")
        e = add_compound(self.conn, "empagliflozin", "class")
        add_atc(self.conn, e, "A10BK03")
        self.assertEqual(names(self.conn, "v_extension_evidence"), set())
        self.assertEqual(names(self.conn, "v_class_entry_basis"), set())

    def test_mechanistic_without_reprogramming_evidence_is_flagged(self):
        add_compound(self.conn, "RepSox", "reprogramming_cocktail")
        problems = {r["canonical_name"]: r["problem"] for r in self.conn.execute("SELECT * FROM v_entry_route_check")}
        self.assertEqual(problems["RepSox"], "mechanistic_without_reprogramming_evidence")

    def test_mechanistic_with_animal_evidence_is_flagged(self):
        m = add_compound(self.conn, "x", "reprogramming_cocktail")
        add_evidence(self.conn, m)
        problems = {r["canonical_name"]: r["problem"] for r in self.conn.execute("SELECT * FROM v_entry_route_check")}
        self.assertEqual(problems["x"], "mechanistic_but_has_animal_evidence")


GOOD_REPRO = dict(source_component_name="E-616452 (6)", citation_pmid="37437248",
                  citation_doi="10.18632/aging.204896", cocktail_name="Yang 2023 C1 (VC6TF)",
                  cocktail_components=json.dumps(["V", "C", "6", "T", "F"]), composition_complete=1,
                  cell_type="senescent human fibroblasts", cell_species="human", in_vivo=0,
                  demonstration_kind="partial_reprogramming_rejuvenation",
                  demonstrated="Restored NCC integrity and reduced transcriptomic age in 4 days, in vitro.",
                  verified_from="full_text", recorded_by="tester", recorded_at="2026-11-11")


class ReprogrammingEvidenceStandard(unittest.TestCase):
    """No bare names: citation, cocktail, cells and what was demonstrated are all required."""

    def setUp(self):
        self.conn = fresh()
        self.cid = add_compound(self.conn, "RepSox", "reprogramming_cocktail")

    def insert(self, **override):
        row = {**GOOD_REPRO, **override, "compound_id": self.cid}
        cols = ", ".join(row)
        self.conn.execute(f"INSERT INTO reprogramming_evidence ({cols}) VALUES ({', '.join('?' * len(row))})",
                          tuple(row.values()))

    def test_complete_row_accepted_and_clears_integrity_check(self):
        self.insert()
        self.assertEqual(list(self.conn.execute("SELECT * FROM v_entry_route_check")), [])

    def test_bare_or_malformed_entries_rejected(self):
        cases = {
            "no citation": dict(citation_pmid=None, citation_doi=None),
            "bad pmid": dict(citation_pmid="PMID37437248"),
            "bad doi": dict(citation_doi="aging.204896"),
            "no cocktail": dict(cocktail_name="  "),
            "single agent": dict(cocktail_components=json.dumps(["RepSox"])),
            "not a list": dict(cocktail_components='"V+C+6"'),
            "no cell type": dict(cell_type=""),
            "token demonstration": dict(demonstrated="worked"),
            "unknown kind": dict(demonstration_kind="regenerative medicine"),
            "unverified source": dict(verified_from="memory"),
            "no recorder": dict(recorded_by=" "),
            "reviewer without date": dict(reviewed_by="Kevin Ferguson", reviewed_at=None),
        }
        for label, override in cases.items():
            with self.assertRaises(sqlite3.IntegrityError, msg=label):
                self.insert(**override)

    def test_doi_alone_is_enough(self):
        self.insert(citation_pmid=None)

    def test_dossier_labels_the_premise(self):
        self.insert()
        r = dict(self.conn.execute("SELECT * FROM v_mechanistic_human_dossier").fetchone())
        self.assertEqual(r["evidence_tier"], "mechanistic_only")
        self.assertIn("Mechanistic premise only", r["premise"])
        self.assertEqual((r["n_cocktails"], r["citations"], r["all_rows_reviewed"]), (1, "PMID:37437248", 0))

    def test_dossier_excludes_measured_compounds_with_cocktail_rows(self):
        vpa = add_compound(self.conn, "valproic acid")
        add_evidence(self.conn, vpa)
        row = {**GOOD_REPRO, "compound_id": vpa, "source_component_name": "valproic acid (V)"}
        self.conn.execute(f"INSERT INTO reprogramming_evidence ({', '.join(row)}) VALUES "
                          f"({', '.join('?' * len(row))})", tuple(row.values()))
        self.assertEqual(names(self.conn, "v_mechanistic_human_dossier"), set())

    def test_dossier_counts_only_systemic_trials(self):
        self.insert()
        self.conn.execute("INSERT INTO trial (nct_id, results_state) VALUES ('NCT1', 'POSTED')")
        self.conn.execute("INSERT INTO trial (nct_id, results_state) VALUES ('NCT2', 'ONGOING')")
        for nct, exposure in (("NCT1", "systemic"), ("NCT2", "local")):
            self.conn.execute("INSERT INTO trial_intervention (nct_id, raw_name, compound_id, systemic_exposure, "
                              "route_rule_version) VALUES (?, 'x', ?, ?, 'r1')", (nct, self.cid, exposure))
        r = dict(self.conn.execute("SELECT * FROM v_mechanistic_human_dossier").fetchone())
        self.assertEqual((r["n_systemic_trials"], r["n_trials_with_results"]), (1, 1))


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
        self.conn.execute("UPDATE animal_evidence SET direction = 'shortening'")
        self.assertEqual(self.basis(self.empa), [])

    def test_unresolved_conflict_never_propagates_through_class(self):
        self.conn.execute("UPDATE animal_evidence SET direction = 'conflict', direction_conflict = 1")
        self.assertEqual(self.basis(self.empa), [])

    def test_direct_compound_marked_class_is_flagged(self):
        add_evidence(self.conn, self.empa)
        self.assertEqual(self.problems()["empagliflozin"], "class_but_has_animal_evidence")


class ResidualAtcClasses(unittest.TestCase):
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


class DirectionConflicts(unittest.TestCase):
    """Conflicting measures go to a human; they count toward no path until resolved."""

    def setUp(self):
        c = self.conn = fresh()
        self.levodopa = add_compound(c, "levodopa")
        add_evidence(c, self.levodopa, direction="extension", species="Caenorhabditis elegans")
        self.row = add_evidence(c, self.levodopa, direction="conflict",
                                avg_direction="null", max_direction="shortening")
        self.key = key_of(c, self.row)

    def test_conflict_is_not_a_harm_candidate(self):
        self.assertEqual(names(self.conn, "v_harm_candidates"), set())

    def test_conflict_is_queued_for_review(self):
        q = [dict(r) for r in self.conn.execute("SELECT * FROM v_direction_review_needed")]
        self.assertEqual([(r["canonical_name"], r["avg_direction"], r["max_direction"]) for r in q],
                         [("levodopa", "null", "shortening")])

    def test_resolution_takes_effect_and_leaves_queue(self):
        review_direction(self.conn, self.key, "shortening")
        self.assertEqual(names(self.conn, "v_harm_candidates"), {"levodopa"})
        self.assertEqual(list(self.conn.execute("SELECT * FROM v_direction_review_needed")), [])

    def test_resolution_to_null_keeps_it_off_the_harm_path(self):
        review_direction(self.conn, self.key, "null")
        self.assertEqual(names(self.conn, "v_harm_candidates"), set())

    def test_review_requires_named_human(self):
        for reviewer in ("", "auto", "Pipeline"):
            with self.assertRaises(sqlite3.IntegrityError, msg=reviewer):
                review_direction(self.conn, self.key, "null", reviewer=reviewer)

    def test_source_error_correction_requires_citation(self):
        ext = add_evidence(self.conn, self.levodopa, direction="extension", sex="F", itp=1, pmid="38041783")
        with self.assertRaises(sqlite3.IntegrityError):
            review_direction(self.conn, key_of(self.conn, ext), "null", reason="source_error")
        review_direction(self.conn, key_of(self.conn, ext), "null", reason="source_error",
                         citation="PMID:38041783 abstract: female lifespan not significantly affected")
        s = dict(self.conn.execute("SELECT * FROM v_itp_summary").fetchone())
        self.assertEqual((s["itp_cohorts_positive"], s["itp_cohorts_total"]), (0, 1))

    def test_resolution_survives_reload(self):
        review_direction(self.conn, self.key, "shortening")
        self.conn.execute("DELETE FROM animal_evidence WHERE id = ?", (self.row,))
        add_evidence(self.conn, self.levodopa, direction="conflict", key=self.key)
        self.assertEqual(names(self.conn, "v_harm_candidates"), {"levodopa"})


class ItpCohorts(unittest.TestCase):
    """Cohort = one sex in one independent experiment; arms in an experiment share a control."""

    def setUp(self):
        c = self.conn = fresh()
        # Aspirin: 2008 one arm per sex; 2019 two dose arms per sex, all null.
        self.asp = add_compound(c, "aspirin")
        add_evidence(c, self.asp, "extension", sex="M", itp=1, pmid="18631321")
        add_evidence(c, self.asp, "null", sex="F", itp=1, pmid="18631321")
        for sex in ("M", "F"):
            for _ in range(2):
                add_evidence(c, self.asp, "null", sex=sex, itp=1, pmid="30916479")
        # Metformin: one experiment, null both sexes, plus non-ITP worm extension.
        self.met = add_compound(c, "metformin")
        add_evidence(c, self.met, "null", sex="M", itp=1, pmid="27312235")
        add_evidence(c, self.met, "null", sex="F", itp=1, pmid="27312235")
        add_evidence(c, self.met, "extension", species="Caenorhabditis elegans")

    def summary(self, cid):
        return dict(self.conn.execute("SELECT * FROM v_itp_summary WHERE compound_id = ?", (cid,)).fetchone())

    def test_arms_cohorts_and_experiments(self):
        s = self.summary(self.asp)
        self.assertEqual(s["itp_experiments"], 2)
        self.assertEqual((s["itp_arms_positive"], s["itp_arms_total"]), (1, 6))
        self.assertEqual((s["itp_cohorts_positive"], s["itp_cohorts_total"]), (1, 4))
        self.assertEqual((s["itp_male_positive"], s["itp_male_total"]), (1, 2))
        self.assertEqual((s["itp_female_positive"], s["itp_female_total"]), (0, 2))

    def test_aspirin_is_weak(self):
        s = self.summary(self.asp)
        self.assertEqual((s["itp_tier"], s["itp_male_tier"], s["itp_female_tier"]), ("weak", "mixed", "none"))
        self.assertEqual(s["meets_itp_threshold"], 1)   # default ≥1 retained; the tier carries strength

    def test_tiers(self):
        cases = {"strong": [("M", "extension"), ("F", "extension")],
                 "mixed": [("M", "extension")],                  # 1/1: single positive, not majority null
                 "weak": [("M", "extension"), ("F", "null"), ("M", "null")]}
        for tier, arms in cases.items():
            cid = add_compound(self.conn, f"tier-{tier}")
            for i, (sex, d) in enumerate(arms):
                add_evidence(self.conn, cid, d, sex=sex, itp=1, pmid=str(1000 + i))
            self.assertEqual(self.summary(cid)["itp_tier"], tier, tier)

    def test_metformin_is_null_cell(self):
        self.assertEqual(self.summary(self.met)["itp_tier"], "none")
        self.assertEqual(names(self.conn, "v_itp_null"), {"metformin"})

    def test_experiment_override_merges_papers(self):
        # If the 2019 arms were the 2008 mice re-reported, cohorts collapse to 2.
        for r in self.conn.execute("SELECT evidence_key FROM animal_evidence WHERE pmid = '30916479'").fetchall():
            self.conn.execute("INSERT INTO itp_experiment_override (evidence_key, experiment_id, reviewed_by, "
                              "reviewed_at) VALUES (?, 'pmid:18631321', 'kf', '2026-11-11')", (r[0],))
        s = self.summary(self.asp)
        self.assertEqual((s["itp_experiments"], s["itp_cohorts_total"]), (1, 2))

    def test_tier_thresholds_are_data(self):
        self.conn.execute("UPDATE analysis_threshold SET value = 1 WHERE name = 'itp_tier_strong_min_positive'")
        self.conn.execute("UPDATE analysis_threshold SET value = 0.2 WHERE name = 'itp_tier_strong_min_fraction'")
        self.assertEqual(self.summary(self.asp)["itp_tier"], "strong")

    def test_extension_view_carries_ratio_and_tier(self):
        r = dict(self.conn.execute("SELECT * FROM v_extension_evidence WHERE compound_id = ?",
                                   (self.asp,)).fetchone())
        self.assertEqual((r["itp_cohorts_positive"], r["itp_cohorts_total"], r["itp_tier"]), (1, 4, "weak"))
        m = dict(self.conn.execute("SELECT * FROM v_extension_evidence WHERE compound_id = ?",
                                   (self.met,)).fetchone())
        self.assertEqual((m["has_mammal_extension"], m["replicated"]), (0, 0))


class ExactDuplicates(unittest.TestCase):
    def test_identical_rows_kept_but_counted_once(self):
        conn = fresh()
        cid = add_compound(conn, "urolithin a")
        add_evidence(conn, cid, species="Caenorhabditis elegans", key="dup")
        add_evidence(conn, cid, species="Caenorhabditis elegans", key="dup")
        self.assertEqual(conn.execute("SELECT count(*) FROM animal_evidence").fetchone()[0], 2)
        r = conn.execute("SELECT n_extension_rows FROM v_extension_evidence").fetchone()
        self.assertEqual(r[0], 1)


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
        self.assertEqual(s["evidence_tier"], "measured_lifespan")
        self.assertEqual((s["still_meets_threshold"], s["evidence_changed_since_review"]), (1, 0))

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
        self.assertEqual((s["still_meets_threshold"], s["evidence_changed_since_review"]), (0, 1))

    def test_paths_never_merge_counts(self):
        ext = dict(self.conn.execute("SELECT * FROM v_extension_evidence WHERE compound_id = ?",
                                     (self.met,)).fetchone())
        harm = self.candidates()["metformin"]
        self.assertEqual(ext["n_extension_rows"], 2)
        self.assertEqual(harm["n_mammal_shortening_rows"], 1)
        self.assertNotIn("n_mammal_shortening_rows", ext)
        self.assertNotIn("n_extension_rows", harm)

    def test_harm_only_compound_absent_from_extension_path(self):
        self.assertEqual(names(self.conn, "v_extension_evidence"), {"metformin"})

    def test_harm_threshold_is_data(self):
        self.conn.execute("UPDATE analysis_threshold SET value = 2 WHERE name = 'harm_min_mammal_shortening_rows'")
        self.assertEqual(self.candidates(), {})


class HarmReviewContext(unittest.TestCase):
    """Reviewer sees ATC class-mates; entry still requires the class-mate's own evidence."""

    def setUp(self):
        c = self.conn = fresh()
        self.rofe = add_compound(c, "rofecoxib")
        add_evidence(c, self.rofe, direction="shortening")
        add_atc(c, self.rofe, "M01AH02")
        self.cele = add_compound(c, "celecoxib")
        add_evidence(c, self.cele, direction="shortening", species="Rattus norvegicus")
        add_atc(c, self.cele, "M01AH01")
        self.valde = add_compound(c, "valdecoxib", "class")
        add_atc(c, self.valde, "M01AH03")
        self.other = add_compound(c, "unrelated")
        add_evidence(c, self.other, direction="shortening")
        add_atc(c, self.other, "A16AX01", status="residual")
        self.other2 = add_compound(c, "residual-mate", "class")
        add_atc(c, self.other2, "A16AX02", status="residual")

    def context(self, candidate):
        return {r["classmate_name"]: dict(r) for r in self.conn.execute(
            "SELECT * FROM v_harm_review_context WHERE candidate_name = ?", (candidate,))}

    def test_classmates_shown_with_their_evidence(self):
        ctx = self.context("rofecoxib")
        self.assertEqual(set(ctx), {"celecoxib", "valdecoxib"})
        self.assertEqual(ctx["celecoxib"]["classmate_mammal_shortening_rows"], 1)
        self.assertEqual(ctx["celecoxib"]["classmate_harm_state"], "unreviewed")
        self.assertEqual(ctx["valdecoxib"]["classmate_harm_state"], "not_a_candidate")
        self.assertEqual(ctx["valdecoxib"]["classmate_evidence_tier"], "inherited_class")

    def test_context_does_not_make_classmates_candidates(self):
        cands = names(self.conn, "v_harm_candidates")
        self.assertNotIn("valdecoxib", cands)

    def test_residual_classes_give_no_context(self):
        self.assertEqual(self.context("unrelated"), {})


if __name__ == "__main__":
    unittest.main()
