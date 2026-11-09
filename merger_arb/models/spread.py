"""Formulas 2–4: gross spread, annual carry, net spread."""


def gross_spread(consideration_value: float, p_target: float) -> float:
    """(Consideration − P(target)) / P(target)."""
    return (consideration_value - p_target) / p_target


def annual_carry(rf: float, effective_ratio: float, p_acquirer: float,
                 p_target: float, shorting_fee: float) -> float:
    """Annual carry of long target / short E acquirer, per $ of target.

    (0 − r_f) − E × (P_acq / P_tgt) × (fee − r_f)
    Long leg is funded at r_f; the short leg earns the rebate (r_f) minus the borrow fee.
    """
    return (0 - rf) - effective_ratio * (p_acquirer / p_target) * (shorting_fee - rf)


def net_spread(gross: float, days_to_close: int, carry: float) -> tuple[float, float]:
    """Returns (net spread to close, annualized net spread)."""
    if days_to_close <= 0:
        raise ValueError("days_to_close must be positive")
    net = gross + (days_to_close / 365) * carry
    return net, net * 365 / days_to_close
