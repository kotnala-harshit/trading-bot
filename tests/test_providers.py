import pandas as pd

from qts.providers import _normalize


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
