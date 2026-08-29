import pytest

from qts.paper import execute_paper_fill, mark_to_market


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
