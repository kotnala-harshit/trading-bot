from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PositionPlan:
    shares: int
    allocation: float
    risk_at_stop: float
    stop_price: float


def size_long_position(
    capital: float,
    price: float,
    *,
    stop_pct: float = 0.05,
    risk_pct: float = 0.005,
    max_allocation_pct: float = 0.15,
) -> PositionPlan:
    if capital <= 0 or price <= 0 or not 0 < stop_pct < 1:
        raise ValueError("Invalid position-sizing inputs")
    shares_by_risk = math.floor(capital * risk_pct / (price * stop_pct))
    shares_by_allocation = math.floor(capital * max_allocation_pct / price)
    shares = max(0, min(shares_by_risk, shares_by_allocation))
    return PositionPlan(shares, shares * price, shares * price * stop_pct, price * (1 - stop_pct))
