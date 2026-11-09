"""Run the full analysis.

Examples:
    python main.py                          # report snapshot only (no internet needed)
    python main.py --history                # fetch prices via yfinance, build exhibits + report
    python main.py --history --source bloomberg
    python main.py --history --csv my_prices.csv
    python main.py --compare                # June vs. November assumptions on the latest close
    python main.py --risk --deal gsat_amzn_nov2026   # hedged-position risk, stress tests, Exhibits 5-6
"""
import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from merger_arb.config.deal_params import DEALS, DEAL_EVENTS, REPORT_SNAPSHOT, RISK_EXCLUDE_DAYS
from merger_arb.data.prices import load_prices, load_csv, load_benchmark
from merger_arb.models import compute_metrics, sensitivity_table, build_time_series, compare_deals
from merger_arb.report.generate_report import write_report
from merger_arb.models import position_risk as pr
from merger_arb.viz.exhibits import make_all, exhibit_5_rolling_vol, exhibit_6_cumulative_pnl


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


COMPARE = {"June 2026": "gsat_amzn", "Nov 2026": "gsat_amzn_nov2026"}
DOLLAR_ROWS = {"consideration", "fail_p_target", "fail_p_acquirer"}


def print_compare(prices):
    """June vs. November assumption sets, both applied to the latest close."""
    as_of, last = prices.index[-1].date(), prices.iloc[-1]
    t = compare_deals({lbl: DEALS[k] for lbl, k in COMPARE.items()},
                      as_of, last.p_target, last.p_acquirer)
    t["change"] = t.iloc[:, 1] - t.iloc[:, 0]

    def fmt(row):
        if row.name in DOLLAR_ROWS:
            return row.map(lambda v: f"${v:,.2f}")
        if row.name in ("close_date", "days_to_close"):
            return row.map(lambda v: "" if isinstance(v, float) and pd.isna(v) else str(v))
        return row.map(lambda v: f"{v:.2%}")

    t.loc[["close_date", "days_to_close"], "change"] = float("nan")
    print(f"\nJune vs. November assumptions — GSAT ${last.p_target:.2f}, "
          f"AMZN ${last.p_acquirer:.2f} on {as_of}\n")
    print(t.apply(fmt, axis=1).to_string())


def _fmt_risk(row):
    if row.name == "minvar_hedge_ratio":
        return row.map(lambda v: f"{v:.4f}")
    if row.name == "n_days":
        return row.map(lambda v: f"{v:.0f}")
    if row.name.endswith("_usd"):
        return row.map(lambda v: f"${v:,.2f}")
    if "beta" in row.name or "corr" in row.name:
        return row.map(lambda v: f"{v:.2f}")
    return row.map(lambda v: f"{v:.2%}")


def run_risk(deal, prices, benchmark, out_dir="output"):
    """Hedged-position risk stats, >3σ day list, stress table, Exhibits 5-6."""
    entry = pr.entry_date(deal, prices.index)
    pnl = pr.hedged_pnl(deal, prices, entry)
    rets = pr.daily_returns(pnl, benchmark)
    E = deal.effective_ratio

    print(f"\n{deal.name}: long 1 {deal.target_ticker} / short {E:.4f} {deal.acquirer_ticker}, "
          f"entered {entry.date()} close (${prices.p_target[entry]:.2f}); "
          f"{len(rets)} daily returns through {rets.index[-1].date()}")
    print(f"Cumulative P&L: ${pnl.cum_pnl.iloc[-1]:.2f}/share "
          f"(of which carry ${pnl.carry.sum():.2f})")

    excl = ", ".join(f"{d} {k}" for k, d in RISK_EXCLUDE_DAYS.items())
    print(f"\nRisk vs. SPY (ex-event days drops: {excl})")
    rep = pr.risk_report(deal, prices, benchmark, list(RISK_EXCLUDE_DAYS.values()))
    print(rep.apply(_fmt_risk, axis=1).to_string())
    print("(var/es: 1-day historical VaR and Expected Shortfall of the hedged position; "
          "negative = loss)")
    h = rep.loc["minvar_hedge_ratio", "all days"]
    print(f"(minvar_*: COMPARISON ONLY, not the hedge we'd use. Shorting {h:.4f} "
          f"{deal.acquirer_ticker} instead of E = {E:.4f} minimizes daily vol in-sample, but "
          f"leaves {E - h:.4f} {deal.acquirer_ticker}/share under-hedged at close, when the "
          f"deal delivers E shares.)")

    print("\nDays with a >3σ move in any series (z-scores):")
    print(pr.outlier_days(rets).round(2).to_string())

    b = pr.gsat_tracking(deal, prices)
    print(f"\nTracking: {deal.target_ticker} moved ${b:.3f} per $1 of "
          f"{deal.acquirer_ticker} (deal terms imply E = {E:.4f})")

    as_of, last = prices.index[-1].date(), prices.iloc[-1]
    st = pr.stress_table(deal, as_of, last.p_target, last.p_acquirer, tracking=b)
    print(f"\nStress tests from {as_of} ({deal.target_ticker} ${last.p_target:.2f}, "
          f"{deal.acquirer_ticker} ${last.p_acquirer:.2f}); fail prices "
          f"${deal.fail_prices.p_target:.2f} / ${deal.fail_prices.p_acquirer:.2f}")
    print(st.to_string(formatters={"pnl_per_share": "${:,.2f}".format,
                                   "return": "{:.2%}".format}))

    var99 = rep.loc["var_99", "all days"]
    brk = st.loc["Deal breaks"]
    print(f"\nThe 1-day 99% historical VaR is a {-var99:.2%} loss "
          f"(${-var99 * last.p_target:.2f}/share), about {brk['return'] / var99:.1f}x smaller "
          f"than the {-brk['return']:.2%} (${-brk.pnl_per_share:.2f}/share) deal-break stress "
          f"loss; historical VaR can't capture a break because none occurred in the sample.")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = [exhibit_5_rolling_vol(rets, deal, out, events=DEAL_EVENTS),
             exhibit_6_cumulative_pnl(pnl, deal, out, entry, events=DEAL_EVENTS)]
    print(f"\nWrote {', '.join(p.name for p in paths)} to {out_dir}/")
    return rep, st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deal", default="gsat_amzn", choices=DEALS)
    ap.add_argument("--history", action="store_true", help="build time series, exhibits, report")
    ap.add_argument("--source", default="yfinance", choices=["yfinance", "bloomberg"])
    ap.add_argument("--csv", help="use a local price CSV instead of fetching")
    ap.add_argument("--refresh", action="store_true", help="ignore the price cache")
    ap.add_argument("--compare", action="store_true",
                    help="June vs. November assumptions side by side on the latest close")
    ap.add_argument("--risk", action="store_true",
                    help="realized risk of the hedged position vs. SPY, stress tests, Exhibits 5-6")
    args = ap.parse_args()
    deal = DEALS[args.deal]

    if args.risk:
        prices = load_csv(args.csv) if args.csv else load_prices(deal, source=args.source,
                                                                  refresh=args.refresh)
        benchmark = load_benchmark(deal.announce_date, source=args.source,
                                   refresh=args.refresh)
        run_risk(deal, prices, benchmark)
        return

    if args.compare:
        prices = load_csv(args.csv) if args.csv else load_prices(deal, source=args.source,
                                                                  refresh=args.refresh)
        print_compare(prices)
        return

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
    exhibits = make_all(ts, deal, "output", events=DEAL_EVENTS)
    report = write_report(deal, latest, scenarios, exhibits, "output")
    print(f"\nWrote {report} and {len(exhibits)} exhibits to output/")


if __name__ == "__main__":
    main()
