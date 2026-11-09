"""Ties formulas 1–7 together for one date, one close scenario, or a full price history."""
from dataclasses import dataclass, asdict
from datetime import date

import pandas as pd

from merger_arb.config.deal_params import DealInputs
from merger_arb.models.consideration import consideration
from merger_arb.models.spread import gross_spread, annual_carry, net_spread
from merger_arb.models.risk import downside, implied_prob_fail, expected_return


@dataclass
class Metrics:
    as_of: date
    close_date: date
    days_to_close: int
    p_target: float
    p_acquirer: float
    consideration: float
    gross_spread: float
    annual_carry: float
    net_spread: float
    ann_net_spread: float
    downside: float
    implied_p_fail: float
    expected_return: float

    def to_dict(self) -> dict:
        return asdict(self)


def compute_metrics(deal: DealInputs, as_of: date, p_target: float,
                    p_acquirer: float, close_date: date | None = None) -> Metrics:
    close_date = close_date or deal.base_close_date
    days = (close_date - as_of).days
    E = deal.effective_ratio

    cons = consideration(deal.effective_cash, E, p_acquirer)
    gross = gross_spread(cons, p_target)
    carry = annual_carry(deal.rf_annual, E, p_acquirer, p_target, deal.shorting_fee_annual)
    net, ann_net = net_spread(gross, days, carry)
    down = downside(deal.fail_prices.p_target, p_target, E,
                    deal.fail_prices.p_acquirer, p_acquirer, carry,
                    deal.days_to_realize_break)

    return Metrics(
        as_of=as_of, close_date=close_date, days_to_close=days,
        p_target=p_target, p_acquirer=p_acquirer, consideration=cons,
        gross_spread=gross, annual_carry=carry, net_spread=net,
        ann_net_spread=ann_net, downside=down,
        implied_p_fail=implied_prob_fail(net, down),
        expected_return=expected_return(deal.prob_fail_assumed, net, down),
    )


def sensitivity_table(deal: DealInputs, as_of: date, p_target: float,
                      p_acquirer: float) -> pd.DataFrame:
    """One row per close-date scenario (base case and extensions)."""
    rows = []
    for label, close in deal.close_scenarios.items():
        m = compute_metrics(deal, as_of, p_target, p_acquirer, close)
        rows.append({"scenario": label, **m.to_dict(),
                     "positive_after_carry": m.ann_net_spread > 0})
    return pd.DataFrame(rows).set_index("scenario")


def compare_deals(deals: dict, as_of: date, p_target: float,
                  p_acquirer: float) -> pd.DataFrame:
    """Same prices, different assumption sets: one column per deal config.

    Rows are the assumptions that differ between configs, then the base-case metrics.
    """
    cols = {}
    for label, deal in deals.items():
        m = compute_metrics(deal, as_of, p_target, p_acquirer)
        cols[label] = {
            "rf_annual": deal.rf_annual,
            "prob_fail_assumed": deal.prob_fail_assumed,
            "fail_p_target": deal.fail_prices.p_target,
            "fail_p_acquirer": deal.fail_prices.p_acquirer,
            **{k: v for k, v in m.to_dict().items()
               if k not in ("as_of", "p_target", "p_acquirer")},
        }
    return pd.DataFrame(cols)


def build_time_series(deal: DealInputs, prices: pd.DataFrame,
                      close_date: date | None = None) -> pd.DataFrame:
    """Run the engine on every trading day.

    `prices` must have a DatetimeIndex and columns p_target, p_acquirer.
    """
    rows = [
        compute_metrics(deal, ts.date(), row.p_target, row.p_acquirer, close_date).to_dict()
        for ts, row in prices.iterrows()
    ]
    out = pd.DataFrame(rows)
    out.index = pd.to_datetime(out.pop("as_of"))
    out.index.name = "date"
    return out
