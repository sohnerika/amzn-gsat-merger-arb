"""Deal input zone: everything specific to one merger-arb deal lives here.

To analyze a different deal, add another DealInputs instance and point
main.py at it. Nothing in models/ should hardcode deal-specific numbers.
"""
from dataclasses import dataclass, field
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

DEALS = {"gsat_amzn": GSAT_AMZN}
