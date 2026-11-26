"""Scaled synonym pipeline (docs/synonym_pipeline.md): filters, collisions, recorded decisions."""
import unittest

from agesdk import scale_identity
from agesdk.scale_synonyms import PubchemFilter, load_rules


class FakePubchem:
    """Stands in for the cached PubChem fetcher: properties() calls get_json()."""

    def __init__(self, props):
        self.props = props

    def get_json(self, endpoint, params=None, **kw):
        cid = int(endpoint.split("/")[2])
        p = self.props.get(cid)
        return (200, {"PropertyTable": {"Properties": [p]}}) if p else (404, None)


class Filters(unittest.TestCase):
    f = PubchemFilter(load_rules())

    def test_real_names_kept(self):
        for s in ["Metformine", "Cidofovir", "vitamin D3", "Dihydromyricetin", "Theelol", "Biotin", "Caffein",
                  "Mushroom sugar", "KU 59436", "16alpha-Hydroxyestradiol"]:
            self.assertIsNotNone(self.f(s)[0], s)

    def test_identifiers_dropped(self):
        for s in ["CHEMBL1431", "DTXSID2023270", "657-24-9", "Q61850", "257-937-5", "C23H24FN3O2", "RefChem:5679",
                  "KBio1_000709", "NCI60_002827", "MEGxp0_000534", "US11866416, Compound SN-II-78", "9100L32L2N",
                  "CN(C)C(=N)N=C(N)N", "InChI=1S/C4H11N5"]:
            self.assertIsNone(self.f(s)[0], s)

    def test_products_and_grades_dropped(self):
        for s in ["Estriol (Standard)", "Estriol 5.0 Cream", "Estriol CRS", "Metformin-d6", "Spermidine (EP)"]:
            self.assertIsNone(self.f(s)[0], s)

    def test_language_tag_stripped_not_dropped(self):
        self.assertEqual(self.f("Estriolo [Italian]")[0], "Estriolo")

    def test_dictionary_filter_is_single_token_only(self):
        self.assertEqual(self.f("Thermal")[1], "dictionary_word")
        self.assertIsNotNone(self.f("Mushroom sugar")[0])


class Decisions(unittest.TestCase):
    ROW = {"drugage_name": "Sodium thiosulfate", "outcome": "mixture", "n_cids": 1, "parent_cid": "", "inchikey": "",
           "formula": "", "pubchem_title": "", "detail": "no PubChem parent for a CID"}
    DEC = {"drugage_name": "Sodium thiosulfate", "decision": "collapse", "target_cid": 1084,
           "target_inchikey": "DHCDFWKWKRSZHF-UHFFFAOYSA-L", "target": "Thiosulfate ion",
           "decided_by": "Kevin Ferguson", "decided_at": "2026-11-26"}

    def test_collapse_resolves_to_recorded_identity(self):
        f = FakePubchem({1084: {"InChIKey": "DHCDFWKWKRSZHF-UHFFFAOYSA-L", "MolecularFormula": "O3S2-2", "Title": "Thiosulfate ion"}})
        r = scale_identity.apply_decision(f, dict(self.ROW), self.DEC)
        self.assertEqual((r["outcome"], r["inchikey"]), ("resolved", "DHCDFWKWKRSZHF-UHFFFAOYSA-L"))

    def test_pubchem_drift_is_refused(self):
        # same first block, different protonation (hydrogen thiosulfate): must not be accepted silently
        f = FakePubchem({1084: {"InChIKey": "DHCDFWKWKRSZHF-UHFFFAOYSA-M", "MolecularFormula": "HO3S2-", "Title": "x"}})
        with self.assertRaises(ValueError):
            scale_identity.apply_decision(f, dict(self.ROW), self.DEC)

    def test_reject_and_leave(self):
        r = scale_identity.apply_decision(None, dict(self.ROW), {**self.DEC, "decision": "reject"})
        self.assertEqual(r["outcome"], "rejected")
        r = scale_identity.apply_decision(None, dict(self.ROW), {**self.DEC, "decision": "leave_unresolved"})
        self.assertEqual(r["outcome"], "mixture")

    def test_bracket_with_components_is_kept(self):
        self.assertEqual(scale_identity.clean_name("PB125 (carnosol, withaferin A and luteolin)"),
                         "PB125 (carnosol, withaferin A and luteolin)")
        self.assertEqual(scale_identity.clean_name("SRT1720 (SIRT1 activator)"), "SRT1720")
        self.assertEqual(scale_identity.clean_name("Ursolic  acid"), "Ursolic acid")


if __name__ == "__main__":
    unittest.main()
