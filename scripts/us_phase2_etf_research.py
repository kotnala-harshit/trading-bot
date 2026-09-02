from __future__ import annotations

import json
import math
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd

from qts.providers import yahoo_chart

ROOT = Path(__file__).resolve().parents[1]
CAPITAL, COST, REVIEW_SESSIONS = 10_000.0, 0.0005, 60
CORE_WEIGHT, SATELLITE_WEIGHT = 0.70, 0.30
UNIVERSE = ("SPY", "QQQ", "IWM", "MDY", "RSP")


def build_backtest(prices: pd.DataFrame) -> pd.DataFrame:
    returns = prices.pct_change(fill_method=None).fillna(0)
    scores = prices.pct_change(63) / (returns.rolling(63).std() * math.sqrt(252))
    scores = scores.where(prices > prices.ewm(span=200).mean()).shift(1)
    satellite = ""
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    for number, day in enumerate(prices.index):
        if number % REVIEW_SESSIONS == 0:
            row = scores.loc[day].replace([np.inf, -np.inf], np.nan).dropna().sort_values(
                ascending=False
            )
            eligible = [symbol for symbol in row[row > 0].index if symbol != "SPY"]
            satellite = satellite if satellite in eligible[:2] else (eligible[0] if eligible else "")
        weights.loc[day, "SPY"] = CORE_WEIGHT
        if satellite:
            weights.loc[day, satellite] = SATELLITE_WEIGHT
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.iloc[0].sum())
    strategy_return = (weights * returns).sum(axis=1) - turnover * COST
    positions = weights.apply(lambda row: ",".join(row[row > 0].index), axis=1)
    return pd.DataFrame(
        {
            "equity": CAPITAL * (1 + strategy_return).cumprod(),
            "benchmark": CAPITAL * (1 + returns.SPY).cumprod(),
            "position": positions,
        }
    )


def metrics(result: pd.DataFrame) -> dict:
    years = (result.index[-1] - result.index[0]).days / 365.25
    growth = result.equity.iloc[-1] / result.equity.iloc[0]
    benchmark_growth = result.benchmark.iloc[-1] / result.benchmark.iloc[0]
    boundaries = list(result.index[result.position.ne(result.position.shift())]) + [result.index[-1]]
    trades = [
        result.loc[end, "equity"] / result.loc[start, "equity"] - 1
        for start, end in pairwise(boundaries)
        if result.loc[start, "position"]
    ]
    return {
        "ending_value_usd": float(CAPITAL * growth),
        "total_return": float(growth - 1),
        "cagr": float(growth ** (1 / years) - 1),
        "max_drawdown": float((result.equity / result.equity.cummax() - 1).min()),
        "win_rate": float(np.mean(np.array(trades) > 0)) if trades else None,
        "closed_allocations": len(trades),
        "spy_total_return": float(benchmark_growth - 1),
        "spy_cagr": float(benchmark_growth ** (1 / years) - 1),
        "spy_max_drawdown": float(
            (result.benchmark / result.benchmark.cummax() - 1).min()
        ),
    }


def main() -> None:
    prices = pd.concat(
        {
            symbol: yahoo_chart(symbol, "10y", "1d").frame.set_index(
                "timestamp"
            ).close.rename(symbol)
            for symbol in UNIVERSE
        }, axis=1, sort=False,
    ).dropna()
    prices.index = prices.index.tz_localize(None).normalize()
    result = build_backtest(prices)
    end = result.index[-1]
    timeline = {
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
        "universe": list(UNIVERSE),
        "strategy": "70% SPY core plus 30% ETF momentum satellite with top-two retention",
        "review_sessions": REVIEW_SESSIONS,
        "exposure": "70% SPY core plus up to 30% satellite",
        "cost_bps_per_weight_change": COST * 10_000,
        "development": metrics(result.loc[:split - pd.Timedelta(days=1)]),
        "holdout": metrics(result.loc[split:]),
        "timeline": timeline,
    }
    (ROOT / "artifacts" / "us_phase2_etf_results.json").write_text(
        json.dumps(output, indent=2, allow_nan=False)
    )
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
