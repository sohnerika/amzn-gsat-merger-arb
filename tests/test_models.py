"""Checks the engine against the numbers in the written report (June 18, 2026 snapshot).

Run with:  python -m unittest   (or pytest, if installed)
"""
import unittest
from datetime import date

import pandas as pd

from merger_arb.config.deal_params import GSAT_AMZN as DEAL, REPORT_SNAPSHOT as SNAP
from merger_arb.models import compute_metrics, sensitivity_table, build_time_series
from merger_arb.models.risk import implied_prob_fail, expected_return


class TestReportNumbers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = compute_metrics(DEAL, SNAP["as_of"], SNAP["p_target"], SNAP["p_acquirer"])

    def test_effective_terms(self):
        self.assertAlmostEqual(DEAL.effective_cash, 36.00, places=2)
        self.assertAlmostEqual(DEAL.effective_ratio, 0.1926, places=4)

    def test_days_to_close(self):
        self.assertEqual(self.m.days_to_close, 299)

    def test_formula_1_consideration(self):
        self.assertAlmostEqual(self.m.consideration, 83.07, places=2)

    def test_formula_2_gross_spread(self):
        self.assertAlmostEqual(self.m.gross_spread, 0.0331, places=4)

    def test_formula_3_carry(self):
        self.assertAlmostEqual(self.m.annual_carry, -0.0204, places=4)

    def test_formula_4_net_spread(self):
        self.assertAlmostEqual(self.m.net_spread, 0.0164, places=4)
        self.assertAlmostEqual(self.m.ann_net_spread, 0.0200, places=4)

    def test_formula_5_downside(self):
        self.assertAlmostEqual(self.m.downside, 0.1279, places=4)

    def test_formula_6_implied_pfail(self):
        # Report: 1.64% / (1.64% + 12.79%) = 11.33% (uses rounded inputs)
        self.assertAlmostEqual(self.m.implied_p_fail, 0.1133, delta=0.0005)

    def test_formula_7_expected_return(self):
        self.assertAlmostEqual(self.m.expected_return, 0.0091, delta=0.0002)


class TestScenarios(unittest.TestCase):
    def test_extensions_reduce_annualized_spread(self):
        s = sensitivity_table(DEAL, SNAP["as_of"], SNAP["p_target"], SNAP["p_acquirer"])
        spreads = s["ann_net_spread"].tolist()
        self.assertEqual(spreads, sorted(spreads, reverse=True))
        # Report: by the April 2028 extension, the trade no longer earns its funding cost
        self.assertFalse(s.loc["second_extension", "positive_after_carry"])


class TestEdgeCases(unittest.TestCase):
    def test_zero_spread_means_zero_implied_pfail(self):
        self.assertEqual(implied_prob_fail(0.0, 0.10), 0.0)

    def test_expected_return_at_implied_pfail_is_zero(self):
        net, down = 0.0164, 0.1279
        self.assertAlmostEqual(expected_return(implied_prob_fail(net, down), net, down), 0.0)

    def test_past_close_date_raises(self):
        with self.assertRaises(ValueError):
            compute_metrics(DEAL, date(2027, 5, 1), 80, 240)

    def test_time_series_shape(self):
        prices = pd.DataFrame({"p_target": [80.41, 81.0], "p_acquirer": [244.39, 246.0]},
                              index=pd.to_datetime(["2026-06-18", "2026-06-19"]))
        ts = build_time_series(DEAL, prices)
        self.assertEqual(len(ts), 2)
        self.assertAlmostEqual(ts.iloc[0]["consideration"], 83.07, places=2)


if __name__ == "__main__":
    unittest.main()
