"""November 2026 update config: loads, keeps the June deal terms, and produces finite metrics."""
import math
import unittest
from datetime import date

from merger_arb.config.deal_params import DEALS, GSAT_AMZN, GSAT_AMZN_NOV2026 as NOV
from merger_arb.models import compute_metrics, sensitivity_table, compare_deals

# Latest close in the cache when the update was written (2026-11-06)
AS_OF, P_T, P_A = date(2026, 11, 6), 84.32, 259.30


class TestNov2026Config(unittest.TestCase):
    def test_registered(self):
        self.assertIs(DEALS["gsat_amzn_nov2026"], NOV)

    def test_same_deal_terms_as_june(self):
        for attr in ("target_ticker", "acquirer_ticker", "announce_date", "cash_per_share",
                     "exchange_ratio", "cash_proration", "close_scenarios"):
            self.assertEqual(getattr(NOV, attr), getattr(GSAT_AMZN, attr), attr)

    def test_metrics_are_finite(self):
        m = compute_metrics(NOV, AS_OF, P_T, P_A)
        for k, v in m.to_dict().items():
            if isinstance(v, float):
                self.assertTrue(math.isfinite(v), k)
        self.assertEqual(m.days_to_close, 158)
        self.assertGreater(m.downside, 0)

    def test_scenarios_are_finite(self):
        s = sensitivity_table(NOV, AS_OF, P_T, P_A)
        self.assertEqual(len(s), 3)
        self.assertTrue(s[["ann_net_spread", "implied_p_fail", "expected_return"]]
                        .map(math.isfinite).all().all())

    def test_compare_has_one_column_per_config(self):
        t = compare_deals({"jun": GSAT_AMZN, "nov": NOV}, AS_OF, P_T, P_A)
        self.assertEqual(list(t.columns), ["jun", "nov"])
        # Same prices, so consideration and gross spread must match across configs
        self.assertEqual(t.loc["consideration", "jun"], t.loc["consideration", "nov"])
        self.assertEqual(t.loc["gross_spread", "jun"], t.loc["gross_spread", "nov"])


if __name__ == "__main__":
    unittest.main()
