from __future__ import annotations

import json
import math
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd

from qts.providers import yahoo_chart

ROOT = Path(__file__).resolve().parents[1]
CAPITAL, EXPOSURE, COST = 1_000_000.0, 0.60, 0.001


def build_backtest(prices: pd.DataFrame) -> pd.DataFrame:
    returns = prices.pct_change(fill_method=None).fillna(0)
    scores = prices.pct_change(63) / (returns.rolling(63).std() * math.sqrt(252))
    scores = scores.where(prices > prices.ewm(span=200).mean()).shift(1)
    positions = pd.Series("CASH", index=prices.index)
    current = "CASH"
    for number, day in enumerate(prices.index):
        if number % 20 == 0:
            row = scores.loc[day].replace([np.inf, -np.inf], np.nan).dropna()
            current = row.idxmax() if not row.empty and row.max() > 0 else "CASH"
        positions.loc[day] = current
    weights = pd.get_dummies(positions).reindex(columns=prices.columns, fill_value=0) * EXPOSURE
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.iloc[0].sum())
    strategy_return = (weights * returns).sum(axis=1) - turnover * COST
    equity = CAPITAL * (1 + strategy_return).cumprod()
    return pd.DataFrame(
        {"equity": equity, "position": positions, "return": strategy_return,
         "nifty": CAPITAL * (1 + returns.NIFTY).cumprod(),
         "spy_inr": CAPITAL * (1 + returns.SPY_INR).cumprod()}
    )


def metrics(result: pd.DataFrame) -> dict:
    years = (result.index[-1] - result.index[0]).days / 365.25
    growth = result.equity.iloc[-1] / result.equity.iloc[0]
    changes = result.position.ne(result.position.shift())
    boundaries = list(result.index[changes]) + [result.index[-1]]
    trades = []
    for start, end in pairwise(boundaries):
        if result.loc[start, "position"] != "CASH":
            trades.append(result.loc[end, "equity"] / result.loc[start, "equity"] - 1)
    return {
        "ending_value_inr": float(CAPITAL * growth),
        "total_return": float(growth - 1),
        "cagr": float(growth ** (1 / years) - 1),
        "max_drawdown": float((result.equity / result.equity.cummax() - 1).min()),
        "win_rate": float(np.mean(np.array(trades) > 0)) if trades else None,
        "closed_trades": len(trades),
        "nifty_cagr": float((result.nifty.iloc[-1] / result.nifty.iloc[0]) ** (1 / years) - 1),
        "spy_inr_cagr": float(
            (result.spy_inr.iloc[-1] / result.spy_inr.iloc[0]) ** (1 / years) - 1
        ),
        "time_in_nifty": float((result.position == "NIFTY").mean()),
        "time_in_us": float((result.position == "SPY_INR").mean()),
        "time_in_cash": float((result.position == "CASH").mean()),
    }


def main() -> None:
    datasets = {
        symbol: yahoo_chart(ticker, "10y", "1d").frame
        for symbol, ticker in {"NIFTY": "^NSEI", "SPY": "SPY", "FX": "INR=X"}.items()
    }
    close = pd.concat(
        {
            symbol: frame.set_index(frame.timestamp.dt.tz_localize(None).dt.normalize()).close
            for symbol, frame in datasets.items()
        }, axis=1, sort=False,
    ).sort_index().ffill().dropna()
    prices = pd.DataFrame({"NIFTY": close.NIFTY, "SPY_INR": close.SPY * close.FX})
    result = build_backtest(prices)
    end = result.index[-1]
    windows = {
        label: metrics(result.loc[max(result.index[0], end - offset):])
        for label, offset in (
            ("3m", pd.DateOffset(months=3)), ("6m", pd.DateOffset(months=6)),
            ("9m", pd.DateOffset(months=9)), ("12m", pd.DateOffset(months=12)),
            ("3y", pd.DateOffset(years=3)), ("5y", pd.DateOffset(years=5)),
            ("10y", pd.DateOffset(years=10)),
        )
    }
    split = result.index[0] + pd.DateOffset(years=5)
    output = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "research_only_not_deployed",
        "starting_capital_inr": CAPITAL,
        "strategy": "20-session rotation between Nifty 50 and adjusted SPY in INR",
        "signal": "63-session risk-adjusted momentum plus 200-day EMA gate",
        "exposure": EXPOSURE,
        "cost_bps_per_weight_change": COST * 10_000,
        "development": metrics(result.loc[:split - pd.Timedelta(days=1)]),
        "holdout": metrics(result.loc[split:]),
        "timeline": windows,
    }
    path = ROOT / "artifacts" / "phase25_results.json"
    path.write_text(json.dumps(output, indent=2, allow_nan=False))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
