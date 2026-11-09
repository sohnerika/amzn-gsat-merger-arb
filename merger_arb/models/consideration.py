"""Formula 1: blended consideration per target share."""


def consideration(effective_cash: float, effective_ratio: float, p_acquirer: float) -> float:
    """C + E × P(acquirer)."""
    return effective_cash + effective_ratio * p_acquirer
