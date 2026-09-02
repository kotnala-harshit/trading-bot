import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.us_phase2_etf_research import CAPITAL, UNIVERSE, build_backtest, metrics


def test_us_etf_research_is_lagged_and_finite():
    dates = pd.date_range("2020-01-01", periods=500, freq="B")
    prices = pd.DataFrame(
        {symbol: range(100 + offset, 600 + offset) for offset, symbol in enumerate(UNIVERSE)},
        index=dates,
    )
    result = build_backtest(prices)
    report = metrics(result)
    assert result.equity.iloc[0] == CAPITAL
    assert report["ending_value_usd"] > CAPITAL
    assert -1 < report["max_drawdown"] <= 0
