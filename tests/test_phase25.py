import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.phase25_research import CAPITAL, build_backtest, metrics


def test_phase25_rotation_is_lagged_and_finite():
    dates = pd.date_range("2020-01-01", periods=500, freq="B")
    prices = pd.DataFrame(
        {"NIFTY": range(100, 600), "SPY_INR": range(600, 100, -1)}, index=dates
    )
    result = build_backtest(prices)
    report = metrics(result)
    assert result.equity.iloc[0] == CAPITAL
    assert report["ending_value_inr"] > CAPITAL
    assert -1 < report["max_drawdown"] <= 0
    assert set(result.position) <= {"NIFTY", "SPY_INR", "CASH"}
