from __future__ import annotations

from dataclasses import dataclass

from qts.broker import Broker, OrderRequest, Quote


@dataclass(frozen=True)
class ReconciliationResult:
    matched: bool
    position_mismatches: dict[str, tuple[int, int]]
    cash_difference: float
    open_orders: int


def executable_price(quote: Quote, side: str, slippage_bps: float = 0.0) -> float:
    """Conservative paper price: cross the spread, then apply adverse slippage."""
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    reference = quote.ask if side == "BUY" and quote.ask else quote.bid if side == "SELL" and quote.bid else quote.last
    direction = 1 if side == "BUY" else -1
    return float(reference) * (1 + direction * slippage_bps / 10_000)


def reconcile_state(state: dict, broker: Broker, cash_tolerance: float = 1.0) -> ReconciliationResult:
    expected = {symbol: int(item["quantity"]) for symbol, item in state.get("positions", {}).items()}
    actual = {symbol: int(qty) for symbol, qty in broker.get_positions().items() if qty}
    mismatches: dict[str, tuple[int, int]] = {}
    for symbol in sorted(set(expected) | set(actual)):
        if expected.get(symbol, 0) != actual.get(symbol, 0):
            mismatches[symbol] = (expected.get(symbol, 0), actual.get(symbol, 0))
    cash_difference = float(state.get("cash", 0.0)) - float(broker.get_cash())
    open_orders = len(broker.get_open_orders())
    matched = not mismatches and abs(cash_difference) <= cash_tolerance and open_orders == 0
    return ReconciliationResult(matched, mismatches, cash_difference, open_orders)


def build_rebalance_orders(current: dict[str, int], target: dict[str, int]) -> list[OrderRequest]:
    """Generate sells before buys so capital is released before new positions are opened."""
    sells, buys = [], []
    for symbol in sorted(set(current) | set(target)):
        delta = int(target.get(symbol, 0)) - int(current.get(symbol, 0))
        if delta < 0:
            sells.append(OrderRequest(symbol=symbol, side="SELL", quantity=-delta))
        elif delta > 0:
            buys.append(OrderRequest(symbol=symbol, side="BUY", quantity=delta))
    return sells + buys
