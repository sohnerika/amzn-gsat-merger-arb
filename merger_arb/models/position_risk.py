"""Realized risk of the hedged position: long 1 target share, short E acquirer shares.

The spread formulas in engine.py say what the trade *should* earn. This module asks how
the position actually behaved day to day: how much the AMZN short cut volatility, how much
market (SPY) exposure was left, and how the position would do under stress.

Conventions
-----------
* Entry: close of the first trading day *after* announcement. The announcement-day close
  is pre-deal, so entering there would count the deal pop as trading P&L.
* Daily P&L ($ per target share): ΔP_tgt − E × ΔP_acq + carry, where carry = the engine's
  annual carry rate × prior-day P_tgt × calendar days / 365 (weekends accrue financing).
* Daily return: P&L ÷ prior-day P_tgt, i.e. return on the capital in the long leg.
* Vol is annualized with √252; beta/correlation are vs. daily benchmark returns.
"""
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from merger_arb.config.deal_params import DealInputs
from merger_arb.models.engine import compute_metrics
from merger_arb.models.spread import annual_carry

TRADING_DAYS = 252


# --- Position P&L ----------------------------------------------------------------

def entry_date(deal: DealInputs, index: pd.DatetimeIndex) -> pd.Timestamp:
    """First trading day strictly after the announcement."""
    after = index[index > pd.Timestamp(deal.announce_date)]
    if after.empty:
        raise ValueError("no trading days after announcement")
    return after[0]


def hedged_pnl(deal: DealInputs, prices: pd.DataFrame, start: pd.Timestamp | None = None,
               hedge_ratio: float | None = None) -> pd.DataFrame:
    """Daily P&L and returns of long 1 target / short `hedge_ratio` acquirer, from entry onward.

    `hedge_ratio` defaults to E (the deal's effective exchange ratio), the hedge we trade.
    `prices`: DatetimeIndex, columns p_target, p_acquirer.
    Returns columns: pnl_target, pnl_hedge, carry, pnl, ret, ret_target, cum_pnl.
    """
    start = start or entry_date(deal, prices.index)
    px = prices.loc[start:, ["p_target", "p_acquirer"]]
    prev = px.shift(1)
    E = deal.effective_ratio if hedge_ratio is None else hedge_ratio

    days = px.index.to_series().diff().dt.days
    carry_rate = annual_carry(deal.rf_annual, E, prev.p_acquirer, prev.p_target,
                              deal.shorting_fee_annual)

    out = pd.DataFrame({
        "pnl_target": px.p_target.diff(),
        "pnl_hedge": -E * px.p_acquirer.diff(),
        "carry": carry_rate * prev.p_target * days / 365,
    })
    out["pnl"] = out.sum(axis=1, min_count=3)
    out["ret"] = out.pnl / prev.p_target
    out["ret_target"] = px.p_target.pct_change()
    out = out.dropna()
    out["cum_pnl"] = out.pnl.cumsum()
    return out


def daily_returns(pnl: pd.DataFrame, benchmark: pd.Series) -> pd.DataFrame:
    """Aligned daily returns: hedged, target alone, benchmark (inner join on dates)."""
    return pd.concat({"hedged": pnl.ret, "target": pnl.ret_target,
                      "benchmark": benchmark.pct_change()}, axis=1, join="inner").dropna()


# --- Statistics ------------------------------------------------------------------

def ann_vol(r: pd.Series) -> float:
    return r.std() * np.sqrt(TRADING_DAYS)


def beta(r: pd.Series, mkt: pd.Series) -> float:
    """OLS slope of r on mkt: cov(r, mkt) / var(mkt)."""
    return r.cov(mkt) / mkt.var()


def downside_beta(r: pd.Series, mkt: pd.Series) -> float:
    """Beta estimated only on days the market fell."""
    down = mkt < 0
    return beta(r[down], mkt[down])


def max_drawdown(cum_pnl: pd.Series) -> float:
    """Largest peak-to-trough fall in cumulative $ P&L (negative number).

    The running peak starts at 0 (entry), so an immediate loss counts as drawdown.
    """
    peak = cum_pnl.cummax().clip(lower=0)
    return (cum_pnl - peak).min()


def historical_var(r: pd.Series, level: float = 0.95) -> float:
    """1-day historical VaR: the (1 − level) quantile of daily returns (a negative number).

    No distribution assumed; it's the empirical cutoff, linearly interpolated between
    observations. With ~140 days, the 99% VaR sits between the worst and 2nd-worst day.
    """
    return r.quantile(1 - level)


def expected_shortfall(r: pd.Series, level: float = 0.95) -> float:
    """1-day historical ES (CVaR): average return on days at or below the VaR cutoff.

    Answers "when it's a bad day, how bad on average?" At 99% on ~140 days this is
    essentially the single worst day, so read it as an anecdote, not an estimate.
    """
    return r[r <= historical_var(r, level)].mean()


def outlier_days(returns: pd.DataFrame, n_sigma: float = 3.0) -> pd.DataFrame:
    """Days where any column moved more than n_sigma full-sample std devs.

    Returns the z-scores for flagged days, so you can see which series triggered it.
    """
    z = (returns - returns.mean()) / returns.std()
    return z[(z.abs() > n_sigma).any(axis=1)]


def risk_summary(returns: pd.DataFrame, cum_pnl: pd.Series, entry_price: float) -> dict:
    h, t, m = returns.hedged, returns.target, returns.benchmark
    dd = max_drawdown(cum_pnl)
    return {
        "n_days": len(returns),
        "vol_hedged": ann_vol(h),
        "vol_target": ann_vol(t),
        "vol_benchmark": ann_vol(m),
        "vol_reduction": 1 - ann_vol(h) / ann_vol(t),
        "corr_vs_benchmark": h.corr(m),
        "beta_vs_benchmark": beta(h, m),
        "downside_beta": downside_beta(h, m),
        "target_beta": beta(t, m),
        "max_drawdown_usd": dd,
        "max_drawdown_pct": dd / entry_price,
        # Hedged position, 1-day, historical; negative = loss (same sign as drawdown)
        **{f"{name}_{lvl:.0%}".replace("%", ""): fn(h, lvl)
           for lvl in (0.95, 0.99)
           for name, fn in (("var", historical_var), ("es", expected_shortfall))},
    }


def min_variance_ratio(deal: DealInputs, prices: pd.DataFrame) -> float:
    """Acquirer shares to short per target share that minimize daily $ P&L variance.

    Minimizing var(ΔP_tgt − h × ΔP_acq) gives h* = cov(ΔP_tgt, ΔP_acq) / var(ΔP_acq),
    the same OLS slope as gsat_tracking(). Estimated in-sample (uses hindsight).
    COMPARISON ONLY: if the deal closes you receive E acquirer shares per target share,
    so shorting h* < E leaves (E − h*) shares of acquirer exposure unhedged at close.
    """
    return gsat_tracking(deal, prices)


def risk_report(deal: DealInputs, prices: pd.DataFrame, benchmark: pd.Series,
                exclude: list[date] = (), min_var_comparison: bool = True) -> pd.DataFrame:
    """Risk stats on all days and with `exclude` (event) days removed.

    With event days removed, P&L on those days is dropped (not just the return),
    so drawdown is recomputed on the remaining path.
    If min_var_comparison, appends the vol of a minimum-variance hedge (comparison only;
    see min_variance_ratio for why we don't trade it).
    """
    entry = entry_date(deal, prices.index)
    entry_price = prices.p_target.loc[entry]
    pnl = hedged_pnl(deal, prices, entry)
    rets = daily_returns(pnl, benchmark)

    drop = pd.DatetimeIndex([pd.Timestamp(d) for d in exclude])
    kept = rets.drop(drop.intersection(rets.index))
    cols = {
        "all days": risk_summary(rets, pnl.pnl.loc[rets.index].cumsum(), entry_price),
        "ex-event days": risk_summary(kept, pnl.pnl.loc[kept.index].cumsum(), entry_price),
    }
    if min_var_comparison:
        h = min_variance_ratio(deal, prices)
        mv = hedged_pnl(deal, prices, entry, hedge_ratio=h).ret
        for col, idx in (("all days", rets.index), ("ex-event days", kept.index)):
            cols[col]["minvar_hedge_ratio"] = h
            cols[col]["minvar_vol"] = ann_vol(mv.loc[idx])
            cols[col]["minvar_vol_reduction"] = 1 - ann_vol(mv.loc[idx]) / ann_vol(rets.target.loc[idx])
    return pd.DataFrame(cols)


# --- Stress tests ----------------------------------------------------------------

def gsat_tracking(deal: DealInputs, prices: pd.DataFrame) -> float:
    """Empirical $ sensitivity of the target to the acquirer: OLS slope of ΔP_tgt on ΔP_acq.

    If the target tracked the stock leg perfectly this would equal E.
    """
    d = prices.loc[entry_date(deal, prices.index):, ["p_target", "p_acquirer"]].diff().dropna()
    return d.p_target.cov(d.p_acquirer) / d.p_acquirer.var()


def stress_table(deal: DealInputs, as_of: date, p_target: float, p_acquirer: float,
                 acquirer_shocks=(-0.10, -0.20), tracking: float | None = None) -> pd.DataFrame:
    """P&L per target share and % return (on p_target) under stress, from `as_of`.

    (a) Deal breaks: both stocks go to the config's fail prices; carry accrues while the
        break plays out (same as the engine's downside formula).
    (b) Close date slips: the deal still closes, at each scenario date. Hedged, so the
        acquirer price at close doesn't matter; P&L = net spread to that date.
    (c) Acquirer drops, deal on track: immediate mark-to-market.
        - "perfect tracking": target moves E × ΔP_acq, so the hedge offsets exactly.
        - "empirical tracking": target moves `tracking` × ΔP_acq (OLS slope from history).
    """
    rows = []
    base = compute_metrics(deal, as_of, p_target, p_acquirer)
    rows.append(("Deal breaks", -base.downside * p_target))

    for label, close in deal.close_scenarios.items():
        m = compute_metrics(deal, as_of, p_target, p_acquirer, close)
        rows.append((f"Closes {close} ({label})", m.net_spread * p_target))

    E = deal.effective_ratio
    for shock in acquirer_shocks:
        d_acq = shock * p_acquirer
        rows.append((f"{deal.acquirer_ticker} {shock:+.0%}, perfect tracking", 0.0))   # (E − E) × ΔP_acq
        if tracking is not None:
            rows.append((f"{deal.acquirer_ticker} {shock:+.0%}, empirical tracking "
                         f"(β$={tracking:.3f})", (tracking - E) * d_acq))

    t = pd.DataFrame(rows, columns=["scenario", "pnl_per_share"]).set_index("scenario")
    t["return"] = t.pnl_per_share / p_target
    return t
