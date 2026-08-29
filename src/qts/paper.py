from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class PaperFill:
    timestamp: str
    symbol: str
    side: str
    quantity: int
    price: float
    fees: float


def execute_paper_fill(
    cash: float,
    position: int,
    *,
    symbol: str,
    side: str,
    quantity: int,
    price: float,
    fee_bps: float = 10,
) -> tuple[float, int, PaperFill]:
    if side not in {"BUY", "SELL"} or quantity < 1 or price <= 0:
        raise ValueError("Invalid paper order")
    notional = quantity * price
    fees = notional * fee_bps / 10_000
    if side == "BUY":
        if notional + fees > cash:
            raise ValueError("Insufficient paper cash")
        cash, position = cash - notional - fees, position + quantity
    else:
        if quantity > position:
            raise ValueError("Paper sell exceeds position")
        cash, position = cash + notional - fees, position - quantity
    fill = PaperFill(datetime.now(UTC).isoformat(), symbol, side, quantity, price, fees)
    return cash, position, fill


def mark_to_market(cash: float, position: int, price: float) -> float:
    return cash + position * price
