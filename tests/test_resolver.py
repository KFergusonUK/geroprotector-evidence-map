import json
import unittest

from agesdk import fixture, resolver
from agesdk.sources import ctgov
from tests.test_ctgov import FakeRegistry, study
from tests.test_schema import fresh

FX = fixture.load()
R = resolver.Resolver(FX)


def decide(name, other_names=None, description=None, arms=None, itype="DRUG"):
    iv = {"name": name, "type": itype}
    if other_names is not None:
        iv["otherNames"] = other_names
    if description is not None:
        iv["description"] = description
    return {r["compound_key"]: r for r in R.resolve_intervention(iv, arms or [])}


class Identity(unittest.TestCase):
    def test_fixture_has_no_violations(self):
        ev = resolver.evaluate_fixture(FX)
        self.assertEqual(ev["violations"], [])
        self.assertGreaterEqual(ev["must_match"].get("auto_accept", 0), 140)

    def test_clean_names_auto_accept(self):
        for s, k in (("Metformin hydrochloride 500 mg extended-release tablets", "metformin"),
                     ("Rapamune 2mg tablet", "rapamycin"), ("BI 10773", "empagliflozin"),
                     ("Dramamine Less Drowsy", "meclizine"), ("Jardiance 10 mg", "empagliflozin")):
            self.assertEqual(decide(s)[k]["decision"], "auto_accept", s)

    def test_rapalogs_and_stereo_traps_never_accepted(self):
        self.assertNotIn("auto_accept", {r["decision"] for r in decide("Everolimus").values()})
        self.assertEqual(decide("Everolimus").get("rapamycin", {}).get("decision"), "rejected")
        self.assertNotIn("17a-estradiol", {k for k, r in decide("Estradiol").items() if r["decision"] != "rejected"})

    def test_ximelagatran_trap(self):
        for s in ("Ximelagatran", "EXANTA", "melagatran/ximelagatran"):
            r = decide(s).get("y27632")
            self.assertTrue(r is None or r["decision"] == "rejected", s)
        self.assertEqual(decide("Ximelegatran")["y27632"]["decision"], "review")   # PubChem's title: review only

    def test_htk_cardioplegia_is_not_akg(self):
        for s in ("Custodiol", "HTK solution", "histidine-tryptophan-ketoglutarate"):
            r = decide(s).get("akg")
            self.assertTrue(r is None or r["decision"] == "rejected", s)

    def test_mesalamine_is_not_aspirin(self):
        self.assertEqual(decide("5-ASA")["aspirin"]["decision"], "rejected")

    def test_combinations_and_qualified_strings_review(self):
        r = decide("Metformin + Sitagliptin")["metformin"]
        self.assertEqual((r["decision"], r["method"]), ("review", "contains"))
        self.assertEqual(decide("Janumet")["metformin"]["decision"], "review")      # needs_review list

    def test_placebo_matching_is_rejected(self):
        r = decide("Empagliflozin-matching placebo")["empagliflozin"]
        self.assertEqual(r["decision"], "rejected")
        self.assertIn("placebo_matching", r["reasons"])

    def test_placebo_for_vs_with(self):
        self.assertEqual(decide("Placebo of clopidogrel and Asprin")["aspirin"]["decision"], "rejected")
        r = decide("Glucophage and placebo")["metformin"]
        self.assertEqual((r["decision"], r["reasons"][-1]), ("review", "placebo_with_compound"))

    def test_own_synonyms_in_brackets_are_clean(self):
        r = decide("Canagliflozin (JNJ-28431754) 100 mg")["canagliflozin"]
        self.assertEqual((r["decision"], r["reasons"]), ("auto_accept", ["only_own_synonyms"]))
        self.assertEqual(decide("Nicotinamide riboside (NIAGEN TM, ChromaDex, CA, USA )")["nr"]["decision"], "review")

    def test_name_and_other_names_agree(self):
        r = decide("NMN supplement", ["nicotinamide mononucleotide"])["nmn"]
        self.assertEqual(r["decision"], "auto_accept")
        self.assertIn("name_and_other_names_agree", r["reasons"])

    def test_route_falls_back_to_study_text(self):
        rows = {r["compound_key"]: r for r in R.resolve_intervention(
            {"name": "Y27632", "type": "DRUG"}, [], "AURN001 in Subjects With Corneal Edema")}
        self.assertEqual(rows["y27632"]["systemic_exposure"], "local")
        self.assertTrue(rows["y27632"]["route_basis"].endswith("(study/arm text)"))

    def test_typo_goes_to_review(self):
        r = decide("Asprin")["aspirin"]
        self.assertEqual((r["decision"], r["method"]), ("review", "fuzzy"))

    def test_short_codes_review(self):
        self.assertEqual(decide("NMN")["nmn"]["decision"], "review")

    def test_polyamine_review_for_spermidine(self):
        self.assertEqual(decide("Polyamine supplementation")["spermidine"]["decision"], "review")


class OtherNames(unittest.TestCase):
    def test_brand_behind_generic_name_auto(self):
        r = decide("Study Drug", ["Glucophage XR"])["metformin"]
        self.assertEqual((r["decision"], r["evidence_field"]), ("auto_accept", "other_names"))

    def test_class_level_name_reviews_even_with_listed_drug(self):
        r = decide("SGLT2 inhibitor", ["Dapagliflozin", "Empagliflozin", "Jardiance"])["empagliflozin"]
        self.assertEqual(r["decision"], "review")
        self.assertIn("class_level_name", r["reasons"])

    def test_kit_of_many_drugs_reviews(self):
        r = decide("Ivermectin", ["Vitamin C", "Quercetin", "Zinc", "Aspirin"])
        self.assertEqual(r["quercetin"]["decision"], "review")
        self.assertIn("multi_compound_other_names", r["quercetin"]["reasons"])

    def test_specific_name_with_other_names_reviews(self):
        r = decide("Vildagliptin", ["Metformin and basal insulin"])["metformin"]
        self.assertEqual(r["decision"], "review")

    def test_description_is_weak(self):
        r = decide("Standard care", description="includes metformin where indicated")["metformin"]
        self.assertEqual((r["decision"], r["evidence_strength"]), ("review", "weak"))


class RouteAndRole(unittest.TestCase):
    def test_route(self):
        self.assertEqual(decide("sirolimus-eluting stent")["rapamycin"]["systemic_exposure"], "local")
        self.assertEqual(decide("Ell-Cranell alpha")["17a-estradiol"]["systemic_exposure"], "local")
        self.assertEqual(decide("Rapamycin", description="topical cream")["rapamycin"]["systemic_exposure"], "local")
        self.assertEqual(decide("Metformin")["metformin"]["systemic_exposure"], "systemic")
        self.assertEqual(decide("Metformin", description="transdermal patch")["metformin"]["systemic_exposure"],
                         "systemic")
        self.assertEqual(decide("Captopril", itype="DEVICE")["captopril"]["systemic_exposure"], "local")
        self.assertEqual(decide("Lithium", description="inhaled")["lithium"]["systemic_exposure"], "unclear")

    def arms(self, *types):
        return [{"label": f"A{i}", "type": t} for i, t in enumerate(types)]

    def role(self, labels, arms):
        return resolver.Resolver.role({"armGroupLabels": labels}, arms)[0]

    def test_roles(self):
        two = self.arms("EXPERIMENTAL", "PLACEBO_COMPARATOR")
        self.assertEqual(self.role(["A0"], two), "experimental")
        self.assertEqual(self.role(["A0", "A1"], two), "background")           # in every arm incl. placebo
        self.assertEqual(self.role(["A1"], self.arms("EXPERIMENTAL", "ACTIVE_COMPARATOR")), "comparator")
        self.assertEqual(self.role(["A0", "A1"], self.arms("EXPERIMENTAL", "EXPERIMENTAL")), "experimental")
        self.assertEqual(self.role(["A0"], self.arms("EXPERIMENTAL")), "experimental")
        self.assertEqual(self.role([], []), "unclear")


class RunOverStaging(unittest.TestCase):
    def test_rows_and_membership_is_not_evidence(self):
        fx = {"fixture_version": "t", "compounds": [
            {"key": "metformin", "role": "seed", "canonical_name": "metformin",
             "must_match": ["metformin", "Glucophage", "Glucophage XR"], "must_not_match": ["phenformin"],
             "needs_review": ["Janumet"], "route_excluded": []}]}
        s = {"NCT1": study("NCT1", [{"type": "DRUG", "name": "Metformin", "armGroupLabels": ["A"]}]),
             "NCT2": study("NCT2", [{"type": "DRUG", "name": "Study Drug", "otherNames": ["Glucophage XR"],
                                     "armGroupLabels": ["A"]}]),
             "NCT3": study("NCT3", [{"type": "DRUG", "name": "Sitagliptin", "armGroupLabels": ["A"]}]),
             "NCT4": study("NCT4", [{"type": "DRUG", "name": "Sitagliptin", "armGroupLabels": ["A"]}])}
        s["NCT3"]["protocolSection"]["identificationModule"]["briefTitle"] = "Sitagliptin added to metformin"
        reg = FakeRegistry(s, {"metformin": ["NCT1", "NCT2", "NCT3", "NCT4"]})
        conn = fresh()
        ctgov.fetch_seed(conn, fx, client=reg)
        resolver.run(conn, fx)
        got = {(r[0], r[1]): r[2] for r in conn.execute("SELECT nct_id, compound_key, decision FROM resolver_match")}
        self.assertEqual(got, {("NCT1", "metformin"): "auto_accept", ("NCT2", "metformin"): "auto_accept",
                               ("NCT3", "metformin"): "background_candidate"})   # NCT4: search hit only, no row
        r = dict(conn.execute("SELECT * FROM resolver_match WHERE nct_id = 'NCT1'").fetchone())
        self.assertEqual((r["role"], r["systemic_exposure"], r["resolver_version"]),
                         ("experimental", "systemic", resolver.load_rules()["version"]))


if __name__ == "__main__":
    unittest.main()


class Step4ErrorClasses(unittest.TestCase):
    """resolver-v2: the four identity errors from the step-4 sample, verbatim, never auto-accepted."""

    def test_the_four_registered_objects(self):
        cases = [
            ("metformin", {"type": "DRUG", "name": "Saxagliptin/Metformin, Fasting", "otherNames": ["Onglyza", "Glucophage"],
                           "description": "Participants received a single oral dose of a fixed dose combination (FDC) "
                                          "tablet of 2.5 mg saxagliptin/500 mg metformin IR under fasting conditions"}),
            ("resveratrol", {"type": "DIETARY_SUPPLEMENT", "name": "Resveratrol",
                             "description": "Daily capsule of 200 mg Polygonum cuspidatum (Solgar®, Dietimport, Lisboa, "
                                            "Portugal) yielding 100 mg/day resveratrol"}),
            ("resveratrol", {"type": "DIETARY_SUPPLEMENT", "name": "Resveratrol",
                             "description": "A blend of low dose resveratrol and either leucine or HMB will be useful "
                                            "nutraceutical strategies"}),
            ("metformin", {"type": "DRUG", "name": "Metformin", "otherNames": ["gliclazide modified release tablets", "acarbose"],
                           "description": "start with metformin，from 500mg bid,if metformin reach the biggest dosage，"
                                          "added gliclazide modified release tablets，afterthat，add acarbose"}),
        ]
        for key, iv in cases:
            r = {x["compound_key"]: x for x in R.resolve_intervention(iv, [])}[key]
            self.assertEqual(r["decision"], "review", iv["name"])


class DescriptionAsymmetry(unittest.TestCase):
    """SPEC §5.1a: the description may only move a match to review or reject, never to accept."""

    def test_description_alone_never_accepts_any_fixture_synonym(self):
        for c in FX["compounds"]:
            for s in c["must_match"]:
                for r in R.resolve_intervention({"type": "DRUG", "name": "Study treatment", "description": s}, []):
                    self.assertNotEqual(r["decision"], "auto_accept", (c["key"], s))

    def test_description_cannot_upgrade_a_review(self):
        r = decide("Metformin + Sitagliptin", description="Metformin")["metformin"]
        self.assertEqual(r["decision"], "review")

    def test_description_cannot_rescue_a_rejection(self):
        r = decide("Everolimus", description="sirolimus")
        self.assertNotEqual(r.get("rapamycin", {}).get("decision"), "auto_accept")

    def test_disqualifier_downgrades(self):
        for desc, why in (("standardised grape extract", "description_extract"),
                          ("fixed-dose combination tablet", "description_fixed_combination"),
                          ("a blend with leucine", "description_blend"),
                          ("then add sitagliptin if needed", "description_regimen")):
            r = decide("Resveratrol", description=desc)["resveratrol"]
            self.assertEqual(r["decision"], "review", desc)
            self.assertIn(why, r["reasons"])

    def test_plain_descriptions_do_not_downgrade(self):
        for desc in ("500 mg twice daily", "Metformin added to standard care", "oral tablets, once daily for 12 weeks"):
            self.assertEqual(decide("Metformin", description=desc)["metformin"]["decision"], "auto_accept", desc)

    def test_other_names_brands_ok_other_drugs_review(self):
        self.assertEqual(decide("Metformin", ["Dabex", "Glucophage"])["metformin"]["decision"], "auto_accept")
        r = decide("Metformin", ["sitagliptin"])["metformin"]
        self.assertEqual(r["decision"], "review")
        self.assertIn("other_names_list_other_drugs", r["reasons"])

    def test_agree_rule_never_on_combination_names(self):
        self.assertEqual(decide("Saxagliptin/Metformin", ["Glucophage"])["metformin"]["decision"], "review")
        self.assertEqual(decide("NMN supplement", ["nicotinamide mononucleotide"])["nmn"]["decision"], "auto_accept")
