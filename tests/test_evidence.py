import unittest

from agesdk.evidence import derive_direction, sex_of_drugage_row


class Direction(unittest.TestCase):
    def check(self, args, expected):
        self.assertEqual(derive_direction(*args), expected, msg=repr(args))

    def test_significant_average_sets_direction(self):
        self.check(("13", "S", "", "NA"), ("extension", "avg"))
        self.check(("-9.8", "S", "", "NA"), ("shortening", "avg"))

    def test_significant_zero_is_null(self):
        self.check(("0", "S", "", "NA"), ("null", "avg"))

    def test_average_wins_over_max(self):
        self.check(("10", "S", "-5", "S"), ("extension", "avg"))

    def test_significant_max_used_when_average_not_significant(self):
        # Levodopa in DrugAge: mean +7% NS, max -14% significant.
        self.check(("7", "NS", "-14", "S"), ("shortening", "max"))
        self.check(("", "NA", "13", "S"), ("extension", "max"))

    def test_not_significant_is_null(self):
        self.check(("7", "NS", "", "NA"), ("null", "avg"))
        self.check(("", "NA", "4", "NS"), ("null", "max"))

    def test_no_significance_reported_is_unassessed_not_null(self):
        # 'null' would turn an untested result into negative evidence.
        self.check(("-23", "NA", "", "NA"), ("unassessed", "none"))
        self.check(("", "", "", ""), ("unassessed", "none"))

    def test_significance_flag_without_value_is_unassessed(self):
        # DrugAge has 'S' rows with no effect size (e.g. Vitamin E): direction unknowable.
        self.check(("", "S", "", "NA"), ("unassessed", "none"))

    def test_garbage_values_do_not_crash(self):
        self.check(("n/a", "S", "", "NA"), ("unassessed", "none"))


class Sex(unittest.TestCase):
    def test_mapping(self):
        for raw, expected in (("Male", "M"), ("Female", "F"), ("Pooled", "both"),
                              ("Hermaphrodite", "hermaphrodite"), ("Unknown", "unknown"), ("", "unknown")):
            self.assertEqual(sex_of_drugage_row({"gender": raw}), expected)


if __name__ == "__main__":
    unittest.main()
