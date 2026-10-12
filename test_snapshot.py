"""Sanity checks for the frozen dataset and reproducible headline calculations."""
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from moveinsync_ratings_monitor import analyze, classify_all, prepare
from build_report import write_store_score_bridge

ROOT = Path(__file__).parent


class SnapshotIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = pd.read_csv(ROOT / "reviews.csv")
        cls.df = prepare(raw)
        cls.tmp = tempfile.TemporaryDirectory()
        analyze(cls.df, meta=None, live=False, out_dir=Path(cls.tmp.name))
        cls.out = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_snapshot_row_count_and_date_range(self):
        self.assertEqual(len(self.df), 24315)
        self.assertEqual(str(self.df["at"].min().date()), "2014-03-14")
        self.assertEqual(str(self.df["at"].max().date()), "2026-10-11")

    def test_submitted_dataset_minimizes_identifiers(self):
        forbidden = {"reviewId", "userName", "userImage", "thumbsUpCount", "replyContent", "repliedAt"}
        self.assertTrue(forbidden.isdisjoint(self.df.columns))
        self.assertTrue({"content", "score", "at", "appVersion", "hasDeveloperReply"}.issubset(self.df.columns))

    def test_headline_rating_windows_reproduce(self):
        w = pd.read_csv(self.out / "rating_windows.csv").set_index("window_days")
        expected = {30: (243, 3.77, 0.272), 90: (721, 3.81, 0.247), 365: (2848, 3.84, 0.240)}
        for days, (n, mean, one) in expected.items():
            self.assertEqual(int(w.loc[days, "reviews"]), n)
            self.assertAlmostEqual(float(w.loc[days, "mean_score"]), mean, delta=0.015)
            self.assertAlmostEqual(float(w.loc[days, "one_star_share"]), one, delta=0.006)

    def test_primary_theme_denominator_and_shares(self):
        t = pd.read_csv(self.out / "theme_summary.csv")
        self.assertEqual(int(t["reviews"].sum()), 843)
        self.assertAlmostEqual(float(t["share_of_low_reviews"].sum()), 1.0, places=8)

    def test_overlapping_mentions_are_separate_from_primary_shares(self):
        m = pd.read_csv(self.out / "theme_mentions.csv").set_index("theme")
        as_of = self.df["at"].max()
        low = self.df[(self.df["at"] > as_of - pd.Timedelta(days=365)) & (self.df["score"] <= 3)]
        expected = {}
        for text in low["content"]:
            for name, _owner in classify_all(text):
                expected[name] = expected.get(name, 0) + 1
        for name, count in expected.items():
            self.assertEqual(int(m.loc[name, "reviews_with_mention"]), count, msg=f"Mismatch for {name}")
        self.assertGreater(int(m["reviews_with_mention"].sum()), len(low))

    def test_impact_scenarios_are_clearly_counterfactual(self):
        impact = pd.read_csv(self.out / "theme_impact_scenarios.csv")
        actionable = impact[impact.actionable_theme]
        self.assertEqual(int(actionable.low_reviews.sum()) + int(impact.loc[~impact.actionable_theme, "low_reviews"].sum()), 843)
        self.assertTrue(actionable.sample_mean_uplift_if_to_4.ge(0).all())
        self.assertTrue(actionable.sample_mean_uplift_if_to_5.ge(actionable.sample_mean_uplift_if_to_4).all())

    def test_store_score_bridge_uses_affected_star_points_not_all_history_rows(self):
        metadata = json.loads((ROOT / "snapshot_metadata.json").read_text(encoding="utf-8"))
        bridge = write_store_score_bridge(metadata, self.df, self.out).set_index("scenario")
        otp = bridge.loc["OTP/login primary theme only"]
        both = bridge.loc["OTP/login + booking primary themes"]
        self.assertEqual(int(otp["primary_theme_reviews_affected"]), 123)
        self.assertEqual(int(otp["star_points_added_if_all_affected_reviews_became_4"]), 331)
        self.assertAlmostEqual(float(otp["naive_equal_weight_whole_listing_score_points"]), 331 / 115000, places=9)
        self.assertEqual(int(both["primary_theme_reviews_affected"]), 234)
        self.assertEqual(int(both["star_points_added_if_all_affected_reviews_became_4"]), 638)
        self.assertAlmostEqual(float(both["naive_equal_weight_whole_listing_score_points"]), 638 / 115000, places=9)

    def test_csv_replay_does_not_write_history(self):
        self.assertFalse((self.out / "history.csv").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
