from __future__ import annotations

import numpy as np
import pandas as pd


def trend_signals(frame: pd.DataFrame, fast: int = 20, slow: int = 80) -> pd.DataFrame:
    if not 1 < fast < slow:
        raise ValueError("Require 1 < fast < slow")
    out = frame.copy()
    out["fast_ma"] = out.close.rolling(fast).mean()
    out["slow_ma"] = out.close.rolling(slow).mean()
    out["signal"] = np.sign(out.fast_ma - out.slow_ma).fillna(0).astype(int)
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
