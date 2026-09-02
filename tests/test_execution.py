import pytest

from qts.broker import OrderRequest, Quote
from qts.execution import build_rebalance_orders, executable_price, reconcile_state


def test_executable_price_crosses_spread_and_adds_adverse_slippage():
    quote = Quote("TCS", last=100, bid=99.9, ask=100.1)
    assert executable_price(quote, "BUY", 10) == pytest.approx(100.2001)
    assert executable_price(quote, "SELL", 10) == pytest.approx(99.8001)


def test_rebalance_sells_before_buys():
    orders = build_rebalance_orders({"A": 10, "B": 5}, {"A": 5, "C": 3})
    assert [(o.symbol, o.side, o.quantity) for o in orders] == [
        ("A", "SELL", 5), ("B", "SELL", 5), ("C", "BUY", 3)
    ]


class FakeBroker:
    def get_positions(self): return {"A": 10}
    def get_cash(self): return 500.0
    def get_open_orders(self): return []


def test_reconciliation_detects_mismatch_and_cash_difference():
    result = reconcile_state({"cash": 510.0, "positions": {"A": {"quantity": 8}}}, FakeBroker())
    assert not result.matched
    assert result.position_mismatches == {"A": (8, 10)}
    assert result.cash_difference == pytest.approx(10)
