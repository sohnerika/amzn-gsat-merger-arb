"""Formulas 5–7: downside, market-implied P(fail), expected return."""


def downside(p_target_fail: float, p_target: float, effective_ratio: float,
             p_acquirer_fail: float, p_acquirer: float, carry: float,
             days_to_realize: int = 14) -> float:
    """Loss (as a positive %) on the hedged position if the deal breaks.

    −[(P_tgt,fail − P_tgt) − E × (P_acq,fail − P_acq)] / P_tgt − (days/365) × carry
    """
    hedged_move = (p_target_fail - p_target) - effective_ratio * (p_acquirer_fail - p_acquirer)
    return -hedged_move / p_target - (days_to_realize / 365) * carry


def implied_prob_fail(net: float, down: float) -> float:
    """Break probability at which the trade is fair: net / (net + downside)."""
    return net / (net + down)


def expected_return(prob_fail: float, net: float, down: float) -> float:
    """(1 − p) × net − p × downside."""
    return (1 - prob_fail) * net - prob_fail * down
