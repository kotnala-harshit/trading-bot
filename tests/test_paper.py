import pytest

from qts.paper import apply_corporate_actions, execute_paper_fill, mark_to_market
from qts.providers import CorporateAction


def test_paper_buy_sell_and_mark_to_market():
    cash, position, _ = execute_paper_fill(
        10_000, 0, symbol="TCS.NS", side="BUY", quantity=2, price=100, fee_bps=10
    )
    assert cash == pytest.approx(9_799.8)
    assert position == 2
    assert mark_to_market(cash, position, 110) == pytest.approx(10_019.8)
    cash, position, sell = execute_paper_fill(
        cash, position, symbol="TCS.NS", side="SELL", quantity=2, price=110, fee_bps=10
    )
    assert position == 0
    assert sell.fees == pytest.approx(0.22)


def test_paper_controls_reject_overspending_and_shorting():
    with pytest.raises(ValueError, match="Insufficient"):
        execute_paper_fill(50, 0, symbol="TCS.NS", side="BUY", quantity=1, price=100)
    with pytest.raises(ValueError, match="exceeds"):
        execute_paper_fill(1_000, 0, symbol="TCS.NS", side="SELL", quantity=1, price=100)


def test_corporate_actions_credit_dividend_adjust_split_and_deduplicate():
    state = {
        "cash": 100.0,
        "positions": {"TCS.NS": {"quantity": 10, "entry_price": 200.0}},
    }
    actions = [
        CorporateAction("div-1", "TCS.NS", "DIVIDEND", "2026-01-01T00:00:00+00:00", 5),
        CorporateAction(
            "split-1", "TCS.NS", "SPLIT", "2026-02-01T00:00:00+00:00",
            numerator=2, denominator=1,
        ),
    ]
    assert len(apply_corporate_actions(state, actions)) == 2
    assert state["cash"] == 150
    assert state["positions"]["TCS.NS"]["quantity"] == 20
    assert state["positions"]["TCS.NS"]["entry_price"] == 100
    assert apply_corporate_actions(state, actions) == []
