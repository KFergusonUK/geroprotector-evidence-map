import unittest

from agesdk.evidence import derive_direction, evidence_key, measure_direction, sex_of_drugage_row


def d(*args):
    r = derive_direction(*args)
    return r.avg, r.max, r.combined


class MeasureDirection(unittest.TestCase):
    def test_per_measure(self):
        self.assertEqual(measure_direction("13", "S"), "extension")
        self.assertEqual(measure_direction("-9.8", "S"), "shortening")
        self.assertEqual(measure_direction("0", "S"), "null")
        self.assertEqual(measure_direction("7", "NS"), "null")
        self.assertEqual(measure_direction("-23", "NA"), "unassessed")
        self.assertEqual(measure_direction("", "S"), "unassessed")      # flag without value
        self.assertEqual(measure_direction("n/a", "S"), "unassessed")


class CombinedDirection(unittest.TestCase):
    def test_single_significant_measure(self):
        self.assertEqual(d("13", "S", "", "NA"), ("extension", "unassessed", "extension"))
        self.assertEqual(d("-9.8", "S", "", "NA"), ("shortening", "unassessed", "shortening"))
        self.assertEqual(d("", "NA", "13", "S"), ("unassessed", "extension", "extension"))

    def test_same_direction_different_significance_is_agreement(self):
        # 17a-estradiol 2014 male: mean +12% S, max +5% NS.
        self.assertEqual(d("12", "S", "5", "NS")[2], "extension")
        # Acarbose 2016 female: mean +2% NS, max +6% S.
        self.assertEqual(d("2", "NS", "6", "S")[2], "extension")

    def test_opposite_directions_are_a_conflict_not_a_precedence(self):
        # Levodopa: mean +7% NS, max -14% S.
        self.assertEqual(d("7", "NS", "-14", "S"), ("null", "shortening", "conflict"))
        # Epitalon: mean -5% NS, max +13% S.
        self.assertEqual(d("-5", "NS", "13", "S")[2], "conflict")
        # Mirror image: mean significant, max points the other way.
        self.assertEqual(d("6", "S", "-1", "NS")[2], "conflict")
        self.assertEqual(d("10", "S", "-5", "S")[2], "conflict")

    def test_unassessed_measure_cannot_conflict(self):
        # Sodium cyclamate: mean +9.77% S, max -11.28% with no significance reported.
        self.assertEqual(d("9.77", "S", "-11.28", "NA")[2], "extension")

    def test_zero_point_estimate_does_not_conflict(self):
        self.assertEqual(d("8", "S", "0", "NS")[2], "extension")

    def test_nothing_significant(self):
        self.assertEqual(d("7", "NS", "-2", "NS")[2], "null")
        self.assertEqual(d("-23", "NA", "", "NA")[2], "unassessed")
        self.assertEqual(d("", "", "", "")[2], "unassessed")


class EvidenceKey(unittest.TestCase):
    def test_stable_and_content_based(self):
        a = {"compound_name": "X", "species": "Mus musculus"}
        self.assertEqual(evidence_key("drugage", a), evidence_key("drugage", dict(reversed(list(a.items())))))
        self.assertNotEqual(evidence_key("drugage", a), evidence_key("drugage", {**a, "species": "Rattus"}))
        self.assertTrue(evidence_key("drugage", a).startswith("drugage:"))


class Sex(unittest.TestCase):
    def test_mapping(self):
        for raw, expected in (("Male", "M"), ("Female", "F"), ("Pooled", "both"),
                              ("Hermaphrodite", "hermaphrodite"), ("Unknown", "unknown"), ("", "unknown")):
            self.assertEqual(sex_of_drugage_row({"gender": raw}), expected)


if __name__ == "__main__":
    unittest.main()
