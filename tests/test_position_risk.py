"""Position-risk module: checked on small synthetic data so the tests need no internet."""
import unittest
from datetime import date

import numpy as np
import pandas as pd

from merger_arb.config.deal_params import GSAT_AMZN_NOV2026 as DEAL
from merger_arb.models import position_risk as pr


def synthetic_prices(n=120, seed=0):
    """AMZN random walk; GSAT tracks the deal consideration (C + E × AMZN) minus a small
    spread, plus small idiosyncratic noise, i.e. a target that trades on the deal terms."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(DEAL.announce_date, periods=n)
    amzn = 250 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    gsat = DEAL.effective_cash + DEAL.effective_ratio * amzn - 1.5 + rng.normal(0, 0.05, n)
    return pd.DataFrame({"p_target": gsat, "p_acquirer": amzn}, index=idx)


class TestHedgedPnl(unittest.TestCase):
    def setUp(self):
        self.px = synthetic_prices()
        self.pnl = pr.hedged_pnl(DEAL, self.px)

    def test_entry_is_day_after_announcement(self):
        entry = pr.entry_date(DEAL, self.px.index)
        self.assertGreater(entry, pd.Timestamp(DEAL.announce_date))
        self.assertEqual(self.pnl.index[0], self.px.index[2])   # first P&L is the day after entry

    def test_daily_pnl_sums_to_position_change(self):
        entry, last = self.px.index[1], self.px.index[-1]
        expected = ((self.px.p_target[last] - self.px.p_target[entry])
                    - DEAL.effective_ratio * (self.px.p_acquirer[last] - self.px.p_acquirer[entry])
                    + self.pnl.carry.sum())
        self.assertAlmostEqual(self.pnl.cum_pnl.iloc[-1], expected, places=9)

    def test_hedged_vol_below_target_vol(self):
        self.assertLess(pr.ann_vol(self.pnl.ret), pr.ann_vol(self.pnl.ret_target))

    def test_min_variance_ratio_recovers_E_when_target_tracks_terms(self):
        # Synthetic GSAT moves exactly E per $1 of AMZN, so the vol-minimizing hedge is E
        self.assertAlmostEqual(pr.min_variance_ratio(DEAL, self.px), DEAL.effective_ratio,
                               delta=0.005)


class TestStats(unittest.TestCase):
    def test_beta_of_series_against_itself_is_one(self):
        r = pd.Series(np.random.default_rng(1).normal(0, 0.01, 250))
        self.assertAlmostEqual(pr.beta(r, r), 1.0, places=12)
        self.assertAlmostEqual(pr.downside_beta(r, r), 1.0, places=12)

    def test_historical_var_and_es(self):
        r = pd.Series(range(-50, 50)) / 1000          # -5.0% ... +4.9%, 100 days
        # 5% quantile sits at position 0.05 × 99 = 4.95 -> between -4.6% and -4.5%
        self.assertAlmostEqual(pr.historical_var(r, 0.95), -0.04505)
        # ES = mean of the 5 days at or below it: -5.0 ... -4.6% -> -4.8%
        self.assertAlmostEqual(pr.expected_shortfall(r, 0.95), -0.048)
        # Tail ordering: 99% is further out than 95%, and ES is at least as bad as VaR
        self.assertLess(pr.historical_var(r, 0.99), pr.historical_var(r, 0.95))
        for lvl in (0.95, 0.99):
            self.assertLessEqual(pr.expected_shortfall(r, lvl), pr.historical_var(r, lvl))

    def test_max_drawdown(self):
        cum = pd.Series([1.0, 3.0, 2.0, -1.0, 0.5, 2.5])
        self.assertAlmostEqual(pr.max_drawdown(cum), -4.0)   # peak 3 -> trough -1
        self.assertAlmostEqual(pr.max_drawdown(pd.Series([-2.0, 1.0])), -2.0)  # loss from entry


class TestStress(unittest.TestCase):
    def setUp(self):
        self.t = pr.stress_table(DEAL, date(2026, 11, 6), 84.32, 259.30, tracking=0.08)

    def test_deal_break_is_a_loss(self):
        self.assertLess(self.t.loc["Deal breaks", "pnl_per_share"], 0)
        self.assertLess(self.t.loc["Deal breaks", "return"], 0)

    def test_close_scenario_pnl_falls_with_delay(self):
        closes = self.t[self.t.index.str.startswith("Closes")].pnl_per_share.tolist()
        self.assertEqual(closes, sorted(closes, reverse=True))

    def test_perfect_tracking_is_hedged(self):
        perfect = self.t[self.t.index.str.contains("perfect")].pnl_per_share
        self.assertTrue((perfect == 0).all())


if __name__ == "__main__":
    unittest.main()
