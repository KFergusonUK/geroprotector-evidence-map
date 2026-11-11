import copy
import unittest

from agesdk import db, fixture
from agesdk.sources import drugage


class FixtureInternal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = fixture.load()

    def by_key(self, fx=None):
        return {c["key"]: c for c in (fx or self.fx)["compounds"]}

    def test_fixture_is_valid(self):
        self.assertEqual(fixture.validate(self.fx), [])

    def test_seed_list_composition(self):
        roles = {}
        for c in self.fx["compounds"]:
            roles.setdefault(c["role"], set()).add(c["key"])
        self.assertEqual(len(roles["seed"]), 18)
        self.assertEqual(roles["class_test_case"], {"empagliflozin", "semaglutide"})
        self.assertEqual(roles["linked_compound"], {"masoprocol"})
        for dropped in ("dasatinib", "glycine-nac", "dasatinib-quercetin"):
            self.assertNotIn(dropped, self.by_key())

    def test_class_test_cases(self):
        k = self.by_key()
        self.assertEqual(k["empagliflozin"]["expected_entry_route"], "class")
        self.assertEqual(k["semaglutide"]["expected_entry_route"], "excluded")

    def test_estradiol_stereo_trap_encoded(self):
        e = self.by_key()["17a-estradiol"]
        self.assertIn("estradiol", e["must_not_match"])
        self.assertIn("17‐alpha‐estradiol", e["must_match"])
        self.assertEqual(len(e["inchikey"]), 27)

    def test_rapalogs_never_match_rapamycin(self):
        self.assertIn("everolimus", self.by_key()["rapamycin"]["must_not_match"])

    def test_ndga_masoprocol_linked_not_merged(self):
        k = self.by_key()
        self.assertEqual(k["ndga"]["same_substance_as"], "masoprocol")
        self.assertEqual(k["masoprocol"]["same_substance_as"], "ndga")
        self.assertNotEqual(k["ndga"]["inchikey"], k["masoprocol"]["inchikey"])
        self.assertIn("masoprocol", k["ndga"]["must_not_match"])

    def test_stents_are_route_excluded_not_identity_excluded(self):
        r = self.by_key()["rapamycin"]
        self.assertIn("sirolimus-eluting stent", r["route_excluded"])
        self.assertNotIn("sirolimus-eluting stent", r["must_not_match"] + r["needs_review"])

    def test_both_path_compounds(self):
        both = {c["key"] for c in self.fx["compounds"]
                if set(c["expected_paths"]) == {"extension", "harm_candidate"}}
        self.assertEqual(both, {"metformin", "canagliflozin", "aspirin", "quercetin"})

    def test_nmn_is_on_no_path(self):
        self.assertEqual(self.by_key()["nmn"]["expected_paths"], [])

    def test_user_decisions_are_attributed(self):
        decided = {c["key"] for c in self.fx["compounds"] if c["decisions"]}
        self.assertTrue({"ndga", "masoprocol", "lithium", "acarbose", "nmn", "aspirin", "rapamycin"} <= decided)

    def test_validator_catches_unreciprocated_link(self):
        fx = copy.deepcopy(self.fx)
        for c in fx["compounds"]:
            if c["key"] == "masoprocol":
                c["same_substance_as"] = None
        self.assertTrue(any("not reciprocated" in e for e in fixture.validate(fx)))

    def test_validator_catches_route_excluded_conflict(self):
        fx = copy.deepcopy(self.fx)
        r = next(c for c in fx["compounds"] if c["key"] == "rapamycin")
        r["must_not_match"].append(r["route_excluded"][0])
        self.assertTrue(any("route_excluded/must_not_match" in e for e in fixture.validate(fx)))

    def test_validator_catches_truncated_inchikey(self):
        fx = copy.deepcopy(self.fx)
        fx["compounds"][0]["inchikey"] = fx["compounds"][0]["inchikey"][:14]
        self.assertTrue(any("27-char" in e for e in fixture.validate(fx)))

    def test_validator_catches_conflicting_lists(self):
        fx = copy.deepcopy(self.fx)
        fx["compounds"][0]["must_not_match"].append(fx["compounds"][0]["must_match"][0])
        self.assertTrue(any("overlap" in e for e in fixture.validate(fx)))

    def test_validator_catches_string_claimed_by_two_compounds(self):
        fx = copy.deepcopy(self.fx)
        fx["compounds"][1]["must_match"].append(fx["compounds"][0]["must_match"][0])
        self.assertTrue(any("also must_match" in e for e in fixture.validate(fx)))

    def test_species_tiers_cover_known_mammals(self):
        tiers = fixture.load_species_tiers()
        for s in ("Mus musculus", "Mus Musculus", "Rattus norvegicus", "Canis lupus familiaris",
                  "Mesocricetus auratus"):
            self.assertEqual(tiers[s], "mammal")
        self.assertEqual(tiers["Caenorhabditis elegans"], "invertebrate")


def _drugage_rows():
    try:
        return drugage.current_rows(db.connect())
    except Exception:
        return None


ROWS = _drugage_rows()


@unittest.skipIf(ROWS is None, "DrugAge not loaded; run `python -m agesdk fetch-drugage`")
class FixtureVsDrugAge(unittest.TestCase):
    """The fixture's claims about DrugAge must match DrugAge as downloaded."""

    def test_fixture_agrees_with_drugage(self):
        problems = fixture.check_against_drugage(fixture.load(), ROWS, fixture.load_species_tiers())
        self.assertEqual(problems, [])

    def test_every_drugage_species_has_a_tier(self):
        tiers = fixture.load_species_tiers()
        self.assertEqual({r["species"] for r in ROWS} - set(tiers), set())

    def test_no_glp1_agonist_in_drugage(self):
        # Basis of the semaglutide negative class test.
        names = " ".join(r["compound_name"].lower() for r in ROWS)
        for drug in ("semaglutide", "liraglutide", "exenatide", "dulaglutide", "lixisenatide", "tirzepatide"):
            self.assertNotIn(drug, names)


if __name__ == "__main__":
    unittest.main()
