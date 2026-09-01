from __future__ import annotations

import numpy as np
import pandas as pd


def trend_signals(frame: pd.DataFrame, fast: int = 20, slow: int = 80) -> pd.DataFrame:
    if not 1 < fast < slow:
        raise ValueError("Require 1 < fast < slow")
    out = frame.copy()
    out["fast_ma"] = out.close.rolling(fast).mean()
    out["slow_ma"] = out.close.rolling(slow).mean()
    out["signal"] = (out.fast_ma > out.slow_ma).fillna(False).astype(int)
    return out


def backtest(
    frame: pd.DataFrame, fast: int = 20, slow: int = 80, cost_bps: float = 1.0
) -> pd.DataFrame:
    out = trend_signals(frame, fast, slow)
    out["return"] = out.close.pct_change().fillna(0)
    out["position"] = out.signal.shift(1).fillna(0)
    out["turnover"] = out.position.diff().abs().fillna(0)
    out["strategy_return"] = out.position * out["return"] - out.turnover * cost_bps / 10_000
    out["equity"] = (1 + out.strategy_return).cumprod()
    out["drawdown"] = out.equity / out.equity.cummax() - 1
    return out


def metrics(result: pd.DataFrame) -> dict[str, float]:
    returns = result.strategy_return
    volatility = returns.std()
    return {
        "total_return_pct": float((result.equity.iloc[-1] - 1) * 100),
        "max_drawdown_pct": float(result.drawdown.min() * 100),
        "sharpe_approx": float((returns.mean() / volatility * np.sqrt(252)) if volatility else 0),
        "trades": int((result.turnover > 0).sum()),
    }


def candidate_score(frame: pd.DataFrame) -> float | None:
    """Rank a stock using only data available at decision time."""
    if len(frame) < 127:
        return None
    signal = trend_signals(frame, fast=20, slow=80).signal.iloc[-1]
    momentum = float(frame.close.iloc[-1] / frame.close.iloc[-126] - 1)
    volatility = float(frame.close.pct_change().tail(60).std() * np.sqrt(252))
    if signal != 1 or momentum <= 0 or not 0 < volatility <= 0.45 or anomaly_risk(frame):
        return None
    return momentum / volatility


def risk_adjusted_momentum_score(frame: pd.DataFrame, lookback: int = 63) -> float | None:
    """Score the long-hold Nifty strategy without requiring a fresh crossover."""
    if len(frame) < lookback + 1:
        return None
    momentum = float(frame.close.iloc[-1] / frame.close.iloc[-lookback - 1] - 1)
    volatility = float(frame.close.pct_change().tail(lookback).std() * np.sqrt(252))
    if not 0 < volatility or anomaly_risk(frame):
        return None
    return momentum / volatility


def anomaly_risk(frame: pd.DataFrame) -> bool:
    """Veto extreme price/volume observations using robust rolling statistics."""
    if len(frame) < 61 or not {"high", "low", "close", "volume"}.issubset(frame.columns):
        return False

    def robust_z(values: pd.Series) -> float:
        history, latest = values.iloc[-61:-1].dropna(), float(values.iloc[-1])
        median = float(history.median())
        deviation = float((history - median).abs().median())
        return abs(latest - median) / max(1.4826 * deviation, 1e-12)

    returns = frame.close.pct_change()
    volume_change = np.log1p(frame.volume).diff()
    intraday_range = (frame.high - frame.low) / frame.close
    return robust_z(returns) > 6 or robust_z(volume_change) > 8 or robust_z(intraday_range) > 8


def market_regime_is_positive(index_frame: pd.DataFrame) -> bool:
    if len(index_frame) < 200:
        return False
    return bool(index_frame.close.iloc[-1] > index_frame.close.tail(200).mean())


def volatility_target_exposure(
    index_frame: pd.DataFrame, target: float = 0.20, floor: float = 0.50
) -> float:
    """Scale equity exposure down when trailing Nifty volatility exceeds the target."""
    if not 0 < floor <= 1 or not 0 < target <= 1:
        raise ValueError("Invalid volatility-target inputs")
    returns = index_frame.close.pct_change().dropna().iloc[-21:-1]
    if len(returns) < 20:
        raise ValueError("Need 21 completed index observations")
    volatility = float(returns.std() * np.sqrt(252))
    return floor if not np.isfinite(volatility) or volatility <= 0 else min(1.0, max(floor, target / volatility))
