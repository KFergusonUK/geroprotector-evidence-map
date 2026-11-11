import unittest
from datetime import date, timedelta

from agesdk import state_backups as sb


def weekly(start, n):
    return [sb.tag_for(start + timedelta(weeks=i), i + 1) for i in range(n)]


class StateBackups(unittest.TestCase):
    def test_tag_round_trip(self):
        t = sb.tag_for(date(2026, 11, 16), 7)
        self.assertEqual(t, "pipeline-state-2026-11-16-run7")
        self.assertEqual(sb.parse(t), (date(2026, 11, 16), 7))
        self.assertIsNone(sb.parse("v0.1"))

    def test_latest_ignores_other_tags(self):
        tags = weekly(date(2026, 11, 16), 3) + ["v1.0", "pipeline-state"]
        self.assertEqual(sb.latest(tags), "pipeline-state-2026-11-30-run3")
        self.assertIsNone(sb.latest(["v1.0"]))

    def test_nothing_pruned_within_twelve(self):
        self.assertEqual(sb.to_prune(weekly(date(2026, 11, 16), 12)), [])

    def test_twelve_weekly_then_monthly(self):
        tags = weekly(date(2026, 1, 5), 52)               # a year of Mondays
        pruned = set(sb.to_prune(tags))
        kept = [t for t in tags if t not in pruned]
        newest12 = sorted(tags, key=sb.parse, reverse=True)[:12]
        self.assertTrue(set(newest12) <= set(kept))
        older = [t for t in kept if t not in newest12]
        months = [sb.parse(t)[0].strftime("%Y-%m") for t in older]
        self.assertEqual(len(months), len(set(months)))     # at most one per month beyond the 12
        newest = sb.latest(tags)
        self.assertNotIn(newest, pruned)
        # every month of the year is still represented
        self.assertEqual({sb.parse(t)[0].month for t in kept}, set(range(1, 13)))

    def test_monthly_keeps_newest_of_the_month(self):
        tags = weekly(date(2025, 1, 6), 40)
        kept = set(tags) - set(sb.to_prune(tags))
        jan = sorted((t for t in kept if sb.parse(t)[0].month == 1 and sb.parse(t)[0].year == 2025), key=sb.parse)
        self.assertEqual(jan, ["pipeline-state-2025-01-27-run4"])

    def test_same_day_reruns_order_by_run_id(self):
        tags = [sb.tag_for(date(2026, 11, 16), 1), sb.tag_for(date(2026, 11, 16), 2)]
        self.assertEqual(sb.latest(tags), "pipeline-state-2026-11-16-run2")


if __name__ == "__main__":
    unittest.main()
