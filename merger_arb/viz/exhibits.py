"""Exhibits 1–4 from the report, drawn from the time-series DataFrame."""
from pathlib import Path

import matplotlib
import pandas as pd
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

TRADING_DAYS = 252

plt.rcParams.update({
    "figure.figsize": (9, 4.5), "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.3, "font.size": 10,
})


def _mark_events(ax, ts, events):
    """Dashed vertical line + label for each dated event inside the plotted range."""
    for label, d in (events or {}).items():
        x = pd.Timestamp(d)
        if ts.index.min() <= x <= ts.index.max():
            ax.axvline(x, color="dimgrey", linestyle="--", linewidth=1)
            ax.annotate(label, xy=(x, 1), xycoords=("data", "axes fraction"),
                        xytext=(-4, -4), textcoords="offset points",
                        ha="right", va="top", fontsize=8, color="dimgrey")


def _finish(fig, ax, title, out: Path, pct=True):
    ax.set_title(title, loc="left", fontweight="bold")
    if pct:
        ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.legend(frameon=False)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def exhibit_1(ts, deal, out_dir: Path):
    fig, ax = plt.subplots()
    ax.plot(ts.index, ts.p_target, label=f"{deal.target_ticker} close")
    ax.plot(ts.index, ts.consideration, label="Blended consideration", linestyle="--")
    ax.set_ylabel("$ per share")
    return _finish(fig, ax, f"Exhibit 1: {deal.target_ticker} price vs. blended consideration",
                   out_dir / "exhibit_1_price_vs_consideration.png", pct=False)


def exhibit_2(ts, deal, out_dir: Path, events=None):
    fig, ax = plt.subplots()
    _mark_events(ax, ts, events)
    ax.plot(ts.index, ts.gross_spread, label="Gross spread")
    ax.plot(ts.index, ts.net_spread, label="Net spread (after carry)")
    return _finish(fig, ax, "Exhibit 2: Gross and net deal spreads",
                   out_dir / "exhibit_2_spreads.png")


def exhibit_3(ts, deal, out_dir: Path, events=None):
    fig, ax = plt.subplots()
    _mark_events(ax, ts, events)
    ax.plot(ts.index, ts.implied_p_fail, label="Market-implied P(fail)")
    ax.axhline(deal.prob_fail_assumed, color="grey", linestyle=":",
               label=f"Our estimate ({deal.prob_fail_assumed * 100:g}%)")
    return _finish(fig, ax, "Exhibit 3: Market-implied probability of failure",
                   out_dir / "exhibit_3_implied_pfail.png")


def exhibit_4(ts, deal, out_dir: Path, events=None):
    fig, ax = plt.subplots()
    _mark_events(ax, ts, events)
    ax.plot(ts.index, ts.net_spread, label="Net spread (deal closes)")
    ax.plot(ts.index, ts.expected_return, label="Expected return")
    ax.plot(ts.index, -ts.downside, label="Return if deal fails")
    ax.axhline(0, color="black", linewidth=0.8)
    return _finish(fig, ax, "Exhibit 4: Net spread, expected return, and failure-state return",
                   out_dir / "exhibit_4_returns.png")


def make_all(ts, deal, out_dir: str | Path = "output", events=None) -> list[Path]:
    """events: {label: date} drawn as dashed lines on Exhibits 2-4.

    Charts start on the first trading day after announcement (the position's entry date),
    matching Exhibits 5-6. The announcement-day close is pre-deal, so its spread and
    implied P(fail) aren't meaningful. The data in `ts` itself is left untouched.
    """
    ts = ts.loc[ts.index > pd.Timestamp(deal.announce_date)]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return [exhibit_1(ts, deal, out_dir),
            *[f(ts, deal, out_dir, events) for f in (exhibit_2, exhibit_3, exhibit_4)]]


# --- Position-risk exhibits (inputs from models/position_risk.py) -------------------

def exhibit_5_rolling_vol(returns, deal, out_dir: Path, window: int = 30, events=None):
    """returns: DataFrame with columns hedged, target, benchmark (daily)."""
    vol = returns.rolling(window).std().dropna() * TRADING_DAYS ** 0.5
    fig, ax = plt.subplots()
    _mark_events(ax, vol, events)
    ax.plot(vol.index, vol.hedged, label=f"Hedged (long {deal.target_ticker} / short "
                                         f"{deal.effective_ratio:.4f} {deal.acquirer_ticker})")
    ax.plot(vol.index, vol.target, label=f"{deal.target_ticker} alone")
    ax.plot(vol.index, vol.benchmark, label="SPY", color="grey")
    return _finish(fig, ax, f"Exhibit 5: {window}-day rolling annualized volatility",
                   out_dir / "exhibit_5_rolling_vol.png")


def exhibit_6_cumulative_pnl(pnl, deal, out_dir: Path, entry, events=None):
    """pnl: DataFrame from hedged_pnl(), with cum_pnl in $ per target share."""
    pnl = pd.concat([pd.DataFrame({"cum_pnl": [0.0]}, index=[entry]), pnl[["cum_pnl"]]])
    fig, ax = plt.subplots()
    _mark_events(ax, pnl, events)
    ax.plot(pnl.index, pnl.cum_pnl, label="Cumulative P&L (incl. carry)")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel(f"$ per {deal.target_ticker} share")
    return _finish(fig, ax, f"Exhibit 6: Cumulative P&L of the hedged position "
                            f"(from {entry:%Y-%m-%d} close)",
                   out_dir / "exhibit_6_cumulative_pnl.png", pct=False)
