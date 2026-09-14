import pandas as pd

from qts.alpaca import parse_quote
from qts.providers import _normalize, _parse_corporate_actions


def test_provider_normalization_orders_and_selects_ohlcv():
    frame = pd.DataFrame(
        {
            "timestamp": ["2026-01-02", "2026-01-01"],
            "open": [2, 1],
            "high": [3, 2],
            "low": [1, 0],
            "close": [2, 1],
            "volume": [20, 10],
            "ignored": [1, 1],
        }
    )
    result = _normalize(frame)
    assert list(result.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert result.close.tolist() == [1, 2]


def test_yahoo_corporate_action_parser():
    result = {
        "events": {
            "dividends": {"100": {"date": 100, "amount": 4.5}},
            "splits": {"200": {"date": 200, "numerator": 2, "denominator": 1}},
        }
    }
    actions = _parse_corporate_actions(result, "TCS.NS")
    assert [(action.kind, action.amount, action.numerator) for action in actions] == [
        ("DIVIDEND", 4.5, 1.0), ("SPLIT", 0.0, 2.0)
    ]


def test_alpaca_quote_uses_iex_bid_ask_midpoint():
    quote = parse_quote({"quote": {"t": "2026-09-01T15:00:00Z", "bp": 100, "ap": 102, "bs": 4, "as": 5}}, "SPY")
    assert (quote.last, quote.provider, quote.bid_size) == (101, "alpaca-iex", 4)
