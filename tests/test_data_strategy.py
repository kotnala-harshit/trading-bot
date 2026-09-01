import pandas as pd
import pytest

from qts.data import load_ohlcv, validate_ohlcv
from qts.strategy import (
    anomaly_risk,
    backtest,
    candidate_score,
    market_regime_is_positive,
    metrics,
    risk_adjusted_momentum_score,
    trend_signals,
    volatility_target_exposure,
)


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


def test_candidate_and_market_regime_filters():
    rising = pd.DataFrame({"close": range(100, 350)})
    assert candidate_score(rising) is not None
    assert market_regime_is_positive(rising)

    falling = rising.copy()
    falling["close"] = list(reversed(rising["close"].tolist()))
    assert candidate_score(falling) is None
    assert not market_regime_is_positive(falling)


def test_risk_adjusted_momentum_accepts_valid_history():
    frame = pd.DataFrame({"close": [100 + index + index % 3 for index in range(80)]})
    assert risk_adjusted_momentum_score(frame) is not None


def test_anomaly_gate_rejects_extreme_price_move():
    frame = pd.DataFrame(
        {
            "close": [100 + index * 0.1 for index in range(60)] + [150],
            "high": [101] * 60 + [155],
            "low": [99] * 60 + [95],
            "volume": [1_000_000] * 60 + [20_000_000],
        }
    )
    assert anomaly_risk(frame)


def test_volatility_target_reduces_exposure_but_keeps_floor():
    calm = pd.DataFrame({"close": [100 * 1.001**day for day in range(30)]})
    volatile = pd.DataFrame({"close": [100 + (-1) ** day * day * 2 for day in range(30)]})
    assert volatility_target_exposure(calm) == 1.0
    assert 0.5 <= volatility_target_exposure(volatile) < 1.0
