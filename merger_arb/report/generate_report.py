"""Writes a short Markdown summary: latest metrics, scenario table, and exhibit links."""
from pathlib import Path

import pandas as pd


def _pct(x):
    return f"{x:.2%}"


def write_report(deal, latest, scenarios: pd.DataFrame, exhibit_paths, out_dir="output") -> Path:
    out_dir = Path(out_dir)
    rec = ("Invest" if latest.expected_return > 0 and latest.implied_p_fail > deal.prob_fail_assumed
           else "Pass")

    table = scenarios[["close_date", "days_to_close", "ann_net_spread", "implied_p_fail",
                       "expected_return", "positive_after_carry"]].copy()
    for c in ("ann_net_spread", "implied_p_fail", "expected_return"):
        table[c] = table[c].map(_pct)

    lines = [
        f"# {deal.name} Merger Arbitrage — as of {latest.as_of}",
        "",
        f"**Recommendation:** {rec} — long {deal.target_ticker} / short "
        f"{deal.effective_ratio:.4f} {deal.acquirer_ticker} per share",
        "",
        "| Metric | Value |", "|---|---|",
        f"| {deal.target_ticker} price | ${latest.p_target:.2f} |",
        f"| {deal.acquirer_ticker} price | ${latest.p_acquirer:.2f} |",
        f"| Blended consideration | ${latest.consideration:.2f} |",
        f"| Gross spread | {_pct(latest.gross_spread)} |",
        f"| Annual carry | {_pct(latest.annual_carry)} |",
        f"| Net spread ({latest.days_to_close} days) | {_pct(latest.net_spread)} |",
        f"| Annualized net spread | {_pct(latest.ann_net_spread)} |",
        f"| Downside if deal fails | {_pct(latest.downside)} |",
        f"| Market-implied P(fail) | {_pct(latest.implied_p_fail)} |",
        f"| Expected return (P(fail) = {deal.prob_fail_assumed:.0%}) | {_pct(latest.expected_return)} |",
        "",
        "## Close-date scenarios",
        "",
        table.to_markdown(),
        "",
        "## Exhibits",
        "",
        *[f"![{p.stem}]({p.name})" for p in exhibit_paths],
    ]
    path = out_dir / "report.md"
    path.write_text("\n".join(lines))
    return path
