# Amazon–Globalstar Merger Arbitrage

Python version of my risk-arbitrage analysis of Amazon's cash-and-stock acquisition of Globalstar (announced April 13, 2026). It models a long GSAT / short AMZN position and computes blended consideration, gross and net spread, carry, downside if the deal breaks, market-implied probability of failure, and expected return, both for a single date and as a daily time series since announcement.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m unittest                 # checks the engine against the report's numbers
python main.py                     # June 18, 2026 report snapshot + close-date scenarios
python main.py --history           # pull prices, build Exhibits 1–4 and output/report.md
```

Other data sources: `--source bloomberg` (needs a Terminal session and `xbbg`) or `--csv prices.csv` (columns `date, p_target, p_acquirer`).

## Layout

```
merger_arb/
  config/deal_params.py   deal terms, scenarios, assumptions (the "input zone")
  data/prices.py          yfinance / Bloomberg / CSV loaders with a local cache
  models/                 formulas 1–7 and the engine that runs them
  viz/exhibits.py         Exhibits 1–4
  report/generate_report.py  Markdown summary
tests/test_models.py      reproduces every number in the written report
main.py                   CLI entry point
```

## Method

With C = prorated cash per share, E = prorated exchange ratio:

1. Consideration = C + E × P(AMZN)
2. Gross spread = (Consideration − P(GSAT)) / P(GSAT)
3. Annual carry = −r_f − E × (P(AMZN)/P(GSAT)) × (borrow fee − r_f)
4. Net spread = Gross + (days/365) × Carry
5. Downside = −[(P(GSAT,fail) − P(GSAT)) − E × (P(AMZN,fail) − P(AMZN))] / P(GSAT) − (14/365) × Carry
6. Implied P(fail) = Net / (Net + Downside)
7. Expected return = (1 − p) × Net − p × Downside

To analyze another deal, add a `DealInputs` entry in `config/deal_params.py` and register it in `DEALS`.
