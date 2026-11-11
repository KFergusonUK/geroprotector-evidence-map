import copy
import unittest

from agesdk import db, reference
from agesdk.reference import load_species
from tests.test_schema import fresh


class ReprogrammingFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = reference.load_reprogramming_spec()

    def comps(self, spec=None):
        return {c["key"]: c for c in (spec or self.spec)["compounds"]}

    def test_file_is_valid(self):
        self.assertEqual(reference.validate_reprogramming(self.spec), [])

    def test_every_cocktail_is_cited_and_described(self):
        for ck in self.spec["cocktails"]:
            cit = self.spec["citations"][ck["citation"]]
            self.assertTrue(cit.get("pmid") or cit.get("doi"), ck["name"])
            self.assertGreaterEqual(len(ck["components_as_written"]), 2)
            self.assertGreaterEqual(len(ck["demonstrated"]), 40)

    def test_unresolved_identities_are_not_verified(self):
        c = self.comps()
        self.assertEqual(c["smoothened_agonist"]["identity_status"], "needs_review")
        self.assertEqual(c["bfgf"]["identity_status"], "needs_review")

    def test_y27632_ximelagatran_trap_encoded(self):
        self.assertIn("ximelagatran", self.comps()["y27632"]["must_not_match"])

    def test_validator_rejects_uncited_cocktail(self):
        spec = copy.deepcopy(self.spec)
        spec["citations"]["yang2023"].pop("pmid")
        spec["citations"]["yang2023"].pop("doi")
        self.assertTrue(any("PMID or DOI" in e for e in reference.validate_reprogramming(spec)))

    def test_validator_rejects_drugage_compound_graded_mechanistic(self):
        spec = copy.deepcopy(self.spec)
        self.comps(spec)["valproic_acid"]["expected_evidence_tier"] = "mechanistic_only"
        self.assertTrue(any("measured_lifespan" in e for e in reference.validate_reprogramming(spec)))

    def test_load_without_drugage(self):
        conn = fresh()
        report = reference.load_reprogramming(conn, self.spec, recorded_at="2026-11-11")
        self.assertEqual(sorted(report["created"]),
                         ["abt869", "chir99021", "forskolin", "repsox", "tranylcypromine", "ttnpb", "y27632"])
        self.assertEqual(sorted(report["skipped_not_loaded"]), ["akg", "butyrate", "valproic_acid"])
        self.assertEqual(sorted(report["skipped_needs_review"]), ["bfgf", "smoothened_agonist"])
        self.assertEqual(list(conn.execute("SELECT * FROM v_entry_route_check")), [])
        again = reference.load_reprogramming(conn, self.spec, recorded_at="2026-11-11")
        self.assertEqual(again["rows_inserted"], 0)
        dossier = {r["canonical_name"]: dict(r) for r in conn.execute("SELECT * FROM v_mechanistic_human_dossier")}
        self.assertEqual(len(dossier), 7)
        self.assertEqual(dossier["RepSox"]["n_cocktails"], 6)
        self.assertTrue(all(d["evidence_tier"] == "mechanistic_only" for d in dossier.values()))


if __name__ == "__main__":
    unittest.main()
