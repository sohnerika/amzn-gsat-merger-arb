"""Price data: fetch from yfinance or Bloomberg, cache to CSV, return a tidy frame.

Output of load_prices(): DatetimeIndex, columns [p_target, p_acquirer].
"""
from datetime import date
from pathlib import Path

import pandas as pd

from merger_arb.config.deal_params import DealInputs

CACHE_DIR = Path(__file__).parent / "cache"


def _cache_path(deal: DealInputs, source: str) -> Path:
    return CACHE_DIR / f"{deal.target_ticker}_{deal.acquirer_ticker}_{source}.csv"


def _fetch_yfinance(deal: DealInputs, start: date, end: date) -> pd.DataFrame:
    import yfinance as yf  # imported lazily so tests don't need it

    raw = yf.download(
        [deal.target_ticker, deal.acquirer_ticker],
        start=start, end=end,
        auto_adjust=False,   # unadjusted closes match quoted prices in the report
        progress=False,
    )["Close"]
    return raw.rename(columns={deal.target_ticker: "p_target",
                               deal.acquirer_ticker: "p_acquirer"})


def _fetch_bloomberg(deal: DealInputs, start: date, end: date) -> pd.DataFrame:
    from xbbg import blp  # requires a live Terminal session

    tickers = {f"{deal.target_ticker} US Equity": "p_target",
               f"{deal.acquirer_ticker} US Equity": "p_acquirer"}
    raw = blp.bdh(list(tickers), "PX_LAST", start, end)
    raw.columns = [tickers[t] for t, _ in raw.columns]
    raw.index = pd.to_datetime(raw.index)
    return raw


FETCHERS = {"yfinance": _fetch_yfinance, "bloomberg": _fetch_bloomberg}


def load_prices(deal: DealInputs, end: date | None = None, source: str = "yfinance",
                refresh: bool = False) -> pd.DataFrame:
    """Load daily closes from announcement to `end`, using the CSV cache when possible."""
    end = end or date.today()
    path = _cache_path(deal, source)

    # Reuse the cache unless asked to refresh; pass refresh=True to pull new days.
    if path.exists() and not refresh:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return df.loc[str(deal.announce_date):str(end)]

    df = FETCHERS[source](deal, deal.announce_date, end)
    df = df[["p_target", "p_acquirer"]].dropna().sort_index()
    df.index.name = "date"
    CACHE_DIR.mkdir(exist_ok=True)
    df.to_csv(path)
    return df


def load_csv(path: str | Path) -> pd.DataFrame:
    """Use your own price file (columns: date, p_target, p_acquirer)."""
    return pd.read_csv(path, index_col="date", parse_dates=True)[["p_target", "p_acquirer"]]
