"""Deal input zone: everything specific to one merger-arb deal lives here.

To analyze a different deal, add another DealInputs instance and point
main.py at it. Nothing in models/ should hardcode deal-specific numbers.
"""
from dataclasses import dataclass, field, replace
from datetime import date


@dataclass(frozen=True)
class FailPrices:
    """Where each stock is assumed to trade if the deal breaks."""
    p_target: float
    p_acquirer: float


@dataclass(frozen=True)
class DealInputs:
    name: str
    target_ticker: str
    acquirer_ticker: str
    announce_date: date

    # Headline terms
    cash_per_share: float          # cash offered per target share
    exchange_ratio: float          # acquirer shares per target share (stock leg)
    cash_proration: float          # fraction of the package paid in cash

    # Timeline scenarios (label -> expected close date)
    close_scenarios: dict = field(default_factory=dict)
    base_case: str = "base"

    # Market / funding assumptions
    rf_annual: float = 0.045
    shorting_fee_annual: float = 0.003
    prob_fail_assumed: float = 0.05
    days_to_realize_break: int = 14   # carry paid while a break plays out

    fail_prices: FailPrices = None

    @property
    def effective_cash(self) -> float:
        """C: prorated cash per target share."""
        return self.cash_proration * self.cash_per_share

    @property
    def effective_ratio(self) -> float:
        """E: prorated acquirer shares per target share."""
        return (1 - self.cash_proration) * self.exchange_ratio

    @property
    def base_close_date(self) -> date:
        return self.close_scenarios[self.base_case]


GSAT_AMZN = DealInputs(
    name="Amazon–Globalstar",
    target_ticker="GSAT",
    acquirer_ticker="AMZN",
    announce_date=date(2026, 4, 13),
    cash_per_share=90.00,
    exchange_ratio=0.3210,
    cash_proration=0.40,
    close_scenarios={
        "base": date(2027, 4, 13),
        "first_extension": date(2027, 10, 13),
        "second_extension": date(2028, 4, 13),
    },
    rf_annual=0.045,
    shorting_fee_annual=0.003,
    prob_fail_assumed=0.05,
    days_to_realize_break=14,
    fail_prices=FailPrices(p_target=61.82, p_acquirer=200.95),
)

# Snapshot used in the written report; tests check the engine against it.
REPORT_SNAPSHOT = {
    "as_of": date(2026, 6, 18),
    "p_target": 80.41,
    "p_acquirer": 244.39,
}

# --- November 2026 update -------------------------------------------------------
# What changed since the June report:
#   * The FCC approved the deal on 2026-10-27, which removed the main regulatory risk.
#     Remaining risks: foreign approvals and Globalstar's HIBLEO-4 satellite milestones.
#   * rf: 4.23% = 6-month Treasury par yield on 2026-11-06 (U.S. Treasury daily curve).
#     The 6-month tenor matches the ~158-day hold to the base-case close better than the 1-year.
#   * P(fail): 5% -> 2.5%. The largest hurdle (FCC) is cleared; execution and
#     foreign-approval risk remain.
#   * Fail prices: GSAT = unaffected 3/30/26 close ($61.82) x SPY's move since then
#     (+16.35%) = $71.93. AMZN = 11/6/26 close ($259.30), because an $11.6B break barely
#     moves Amazon. (June's 18% AMZN drop *lowered* the modeled downside, since the
#     position is short AMZN.)
#   * Close scenarios unchanged: no official earlier date, and Globalstar still ties
#     the closing to 2027 satellite milestones.
# Deal terms (cash, ratio, proration, dates) are identical to GSAT_AMZN.
GSAT_AMZN_NOV2026 = replace(
    GSAT_AMZN,
    name="Amazon–Globalstar (Nov 2026 update)",
    rf_annual=0.0423,
    prob_fail_assumed=0.025,
    fail_prices=FailPrices(p_target=71.93, p_acquirer=259.30),
)

# Dated events to mark on the time-series exhibits.
DEAL_EVENTS = {"FCC approval": date(2026, 10, 27)}

# Days dropped in the "ex-event days" risk stats (position_risk.risk_report).
# 7/31 was the only >3σ move in the hedged position itself (AMZN +15.3%, likely earnings).
# The >3σ SPY days (6/5, 11/5) stay in, because they carry the market-risk information
# that beta and downside beta are measuring.
RISK_EXCLUDE_DAYS = {
    "FCC approval": date(2026, 10, 27),
    "AMZN +15% move": date(2026, 7, 31),
}

DEALS = {"gsat_amzn": GSAT_AMZN, "gsat_amzn_nov2026": GSAT_AMZN_NOV2026}
