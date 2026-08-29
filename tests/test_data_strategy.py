import pytest

from qts.data import load_ohlcv, validate_ohlcv
from qts.strategy import backtest, metrics, trend_signals


def test_sample_data_valid():
    assert validate_ohlcv(load_ohlcv("data/sample/mes_demo.csv")).valid


def test_backtest_is_causal_and_finite():
    result = backtest(load_ohlcv("data/sample/mes_demo.csv"), 3, 8)
    assert result.equity.notna().all()
    assert result.position.iloc[0] == 0
    assert set(metrics(result)) == {
        "total_return_pct",
        "max_drawdown_pct",
        "sharpe_approx",
        "trades",
    }


def test_invalid_parameters_rejected():
    with pytest.raises(ValueError):
        trend_signals(load_ohlcv("data/sample/mes_demo.csv"), 10, 5)
