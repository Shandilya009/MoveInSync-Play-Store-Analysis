"""Regression tests for conservative weekly alert thresholds."""
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from moveinsync_ratings_monitor import build_alerts, prepare


class MonitorAlertTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        dates = pd.date_range("2026-10-01", "2026-10-13", periods=120)
        self.df_low = prepare(pd.DataFrame({
            "content": ["otp not received cannot login"] * 120,
            "score": [2] * 120,
            "at": dates,
            "appVersion": ["10.50.0"] * 120,
            "hasDeveloperReply": [False] * 120,
        }))
        self.metrics_low = [
            {"window_days": 30, "reviews": 120, "mean_score": 2.0},
            {"window_days": 90, "reviews": 120, "mean_score": 2.0},
            {"window_days": 365, "reviews": 120, "mean_score": 2.0},
        ]
        self.versions_low = pd.DataFrame([{
            "appVersion": "10.50.0", "reviews": 30, "mean_score": 3.4,
            "one_star_share": 0.3,
        }])

    def tearDown(self):
        self.tmp.cleanup()

    def _seed_history(self, n=120, mean=4.0, theme_share=0.05, theme_count=6):
        pd.DataFrame([{
            "run_date": "2026-10-12", "avg_30d": mean, "n_30d": n,
            "theme_share_30d_otp_login_session": theme_share,
            "theme_count_30d_otp_login_session": theme_count,
        }]).to_csv(self.out / "history.csv", index=False)

    def test_emits_score_drop_version_and_theme_alerts(self):
        self._seed_history()
        result = build_alerts(self.out, "2026-10-13", self.df_low, self.metrics_low,
                              self.versions_low, pd.DataFrame())
        alerts = result["alert"].tolist()
        self.assertTrue(any("30-day written mean fell" in x for x in alerts))
        self.assertTrue(any("Version score below 3.5" in x for x in alerts))
        self.assertTrue(any("Theme share doubled" in x for x in alerts))

    def test_suppresses_score_drop_with_small_history_sample(self):
        self._seed_history(n=99, mean=4.0)
        versions = pd.DataFrame([{
            "appVersion": "10.50.0", "reviews": 29, "mean_score": 3.2,
            "one_star_share": 0.35,
        }])
        result = build_alerts(self.out, "2026-10-13", self.df_low, self.metrics_low,
                              versions, pd.DataFrame())
        alerts = result["alert"].tolist()
        self.assertFalse(any("30-day written mean fell" in x for x in alerts))
        self.assertFalse(any("Version score below 3.5" in x for x in alerts))

    def test_no_prior_history_does_not_claim_a_drop(self):
        result = build_alerts(self.out, "2026-10-13", self.df_low, self.metrics_low,
                              pd.DataFrame(columns=["appVersion", "reviews", "mean_score", "one_star_share"]),
                              pd.DataFrame())
        self.assertFalse(any("30-day written mean fell" in x for x in result["alert"].tolist()))
        self.assertTrue(any("No threshold crossed" in x for x in result["alert"].tolist()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
