"""Run the full analysis.

Examples:
    python main.py                          # report snapshot only (no internet needed)
    python main.py --history                # fetch prices via yfinance, build exhibits + report
    python main.py --history --source bloomberg
    python main.py --history --csv my_prices.csv
"""
import argparse
from datetime import date

import pandas as pd

from merger_arb.config.deal_params import DEALS, REPORT_SNAPSHOT
from merger_arb.data.prices import load_prices, load_csv
from merger_arb.models import compute_metrics, sensitivity_table, build_time_series
from merger_arb.report.generate_report import write_report
from merger_arb.viz.exhibits import make_all


def print_snapshot(deal, as_of, p_t, p_a):
    m = compute_metrics(deal, as_of, p_t, p_a)
    print(f"\n{deal.name} — as of {as_of}")
    for k in ("consideration", "gross_spread", "annual_carry", "net_spread",
              "ann_net_spread", "downside", "implied_p_fail", "expected_return"):
        v = getattr(m, k)
        print(f"  {k:<18} {'$' + format(v, '.2f') if k == 'consideration' else format(v, '.2%')}")
    print("\nClose-date scenarios:")
    s = sensitivity_table(deal, as_of, p_t, p_a)
    print(s[["days_to_close", "ann_net_spread", "implied_p_fail", "expected_return", "positive_after_carry"]]
          .to_string(float_format=lambda x: f"{x:.2%}"))
    return m, s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deal", default="gsat_amzn", choices=DEALS)
    ap.add_argument("--history", action="store_true", help="build time series, exhibits, report")
    ap.add_argument("--source", default="yfinance", choices=["yfinance", "bloomberg"])
    ap.add_argument("--csv", help="use a local price CSV instead of fetching")
    ap.add_argument("--refresh", action="store_true", help="ignore the price cache")
    args = ap.parse_args()
    deal = DEALS[args.deal]

    if not args.history:
        s = REPORT_SNAPSHOT
        print_snapshot(deal, s["as_of"], s["p_target"], s["p_acquirer"])
        return

    prices = load_csv(args.csv) if args.csv else load_prices(deal, source=args.source,
                                                              refresh=args.refresh)
    ts = build_time_series(deal, prices)
    ts.to_csv("output/time_series.csv")

    last = prices.iloc[-1]
    latest, scenarios = print_snapshot(deal, prices.index[-1].date(),
                                       last.p_target, last.p_acquirer)
    exhibits = make_all(ts, deal, "output")
    report = write_report(deal, latest, scenarios, exhibits, "output")
    print(f"\nWrote {report} and {len(exhibits)} exhibits to output/")


if __name__ == "__main__":
    main()
