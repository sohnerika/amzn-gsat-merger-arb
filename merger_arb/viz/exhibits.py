"""Exhibits 1–4 from the report, drawn from the time-series DataFrame."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

plt.rcParams.update({
    "figure.figsize": (9, 4.5), "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.3, "font.size": 10,
})


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


def exhibit_2(ts, deal, out_dir: Path):
    fig, ax = plt.subplots()
    ax.plot(ts.index, ts.gross_spread, label="Gross spread")
    ax.plot(ts.index, ts.net_spread, label="Net spread (after carry)")
    return _finish(fig, ax, "Exhibit 2: Gross and net deal spreads",
                   out_dir / "exhibit_2_spreads.png")


def exhibit_3(ts, deal, out_dir: Path):
    fig, ax = plt.subplots()
    ax.plot(ts.index, ts.implied_p_fail, label="Market-implied P(fail)")
    ax.axhline(deal.prob_fail_assumed, color="grey", linestyle=":",
               label=f"Our estimate ({deal.prob_fail_assumed:.0%})")
    return _finish(fig, ax, "Exhibit 3: Market-implied probability of failure",
                   out_dir / "exhibit_3_implied_pfail.png")


def exhibit_4(ts, deal, out_dir: Path):
    fig, ax = plt.subplots()
    ax.plot(ts.index, ts.net_spread, label="Net spread (deal closes)")
    ax.plot(ts.index, ts.expected_return, label="Expected return")
    ax.plot(ts.index, -ts.downside, label="Return if deal fails")
    ax.axhline(0, color="black", linewidth=0.8)
    return _finish(fig, ax, "Exhibit 4: Net spread, expected return, and failure-state return",
                   out_dir / "exhibit_4_returns.png")


def make_all(ts, deal, out_dir: str | Path = "output") -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return [f(ts, deal, out_dir) for f in (exhibit_1, exhibit_2, exhibit_3, exhibit_4)]
