from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from qts.providers import CorporateAction


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


def apply_corporate_actions(state: dict, actions: list[CorporateAction]) -> list[str]:
    """Apply unseen actions to held paper positions and return audit messages."""
    processed = set(state.setdefault("processed_corporate_actions", []))
    messages = []
    for action in actions:
        position = state.get("positions", {}).get(action.symbol)
        if action.event_id in processed or not position:
            continue
        opened_at = position.get("opened_at")
        if opened_at and action.timestamp < opened_at:
            continue
        if action.kind == "DIVIDEND" and action.amount > 0:
            credit = position["quantity"] * action.amount
            state["cash"] += credit
            state["dividends_received"] = state.get("dividends_received", 0.0) + credit
            messages.append(f"{action.symbol} dividend ₹{credit:.2f} credited for reinvestment")
        elif action.kind == "SPLIT" and action.numerator > 0 and action.denominator > 0:
            ratio = action.numerator / action.denominator
            position["quantity"] *= ratio
            position["entry_price"] /= ratio
            messages.append(f"{action.symbol} quantity adjusted {action.numerator:g}:{action.denominator:g}")
        else:
            continue
        processed.add(action.event_id)
    state["processed_corporate_actions"] = sorted(processed)
    return messages
