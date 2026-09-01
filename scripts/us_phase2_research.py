from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from qts.providers import yahoo_chart

ROOT = Path(__file__).resolve().parents[1]
CAPITAL = 1_000_000.0
COST = 0.0005


def simulate(frames: dict[str, pd.DataFrame], benchmark: pd.DataFrame, start, end) -> dict:
    calendar = pd.DatetimeIndex(benchmark.timestamp.dt.tz_localize(None)).normalize()
    calendar = calendar[(calendar >= start) & (calendar <= end)]
    close = pd.DataFrame(
        {symbol: frame.set_index(frame.timestamp.dt.tz_localize(None).dt.normalize()).close
         for symbol, frame in frames.items()}
    ).reindex(calendar)
    opens = pd.DataFrame(
        {symbol: frame.set_index(frame.timestamp.dt.tz_localize(None).dt.normalize()).open
         for symbol, frame in frames.items()}
    ).reindex(calendar)
    index = benchmark.set_index(benchmark.timestamp.dt.tz_localize(None).dt.normalize()).close.reindex(calendar)
    returns = close.pct_change(fill_method=None)
    scores = (close.pct_change(63) / (returns.rolling(63).std() * math.sqrt(252))).shift(1)
    exposure = (0.20 / (index.pct_change().rolling(20).std().shift(1) * math.sqrt(252))).clip(0.5, 1)
    cash, positions, entries, trades, last_review = CAPITAL, {}, {}, [], -60
    curve = []
    for day_number, day in enumerate(calendar):
        po, pc = opens.loc[day], close.loc[day]
        prices = {symbol: float(po[symbol]) for symbol in positions if pd.notna(po[symbol])}
        if len(prices) != len(positions):
            continue
        equity = cash + sum(quantity * prices[symbol] for symbol, quantity in positions.items())
        target = float(exposure.loc[day]) if pd.notna(exposure.loc[day]) else 0.5
        invested = equity - cash
        if invested > equity * target * 1.02:
            keep_fraction = equity * target / invested
            for symbol, quantity in list(positions.items()):
                sell = quantity - math.floor(quantity * keep_fraction)
                if sell:
                    cash += sell * prices[symbol] * (1 - COST)
                    positions[symbol] -= sell
        if not positions or day_number - last_review >= 60:
            ranked = list(scores.loc[day].replace([np.inf, -np.inf], np.nan).dropna().nlargest(10).index)
            keep = set(ranked)
            for symbol, quantity in list(positions.items()):
                if symbol not in keep and pd.notna(po[symbol]):
                    cash += quantity * po[symbol] * (1 - COST)
                    trades.append(po[symbol] / entries[symbol] - 1 - 2 * COST)
                    del positions[symbol], entries[symbol]
            for symbol in [item for item in ranked[:5] if item not in positions]:
                if len(positions) >= 5 or pd.isna(po[symbol]):
                    continue
                allocation = equity * target / 5
                quantity = min(
                    math.floor(allocation / (po[symbol] * (1 + COST))),
                    math.floor(cash / (po[symbol] * (1 + COST))),
                )
                if quantity:
                    cash -= quantity * po[symbol] * (1 + COST)
                    positions[symbol], entries[symbol] = quantity, po[symbol]
            last_review = day_number
        marked = cash + sum(
            quantity * (pc[symbol] if pd.notna(pc[symbol]) else po[symbol])
            for symbol, quantity in positions.items()
        )
        curve.append((day, marked))
    equity = pd.Series(dict(curve))
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    daily = equity.pct_change().dropna()
    benchmark_years = (index.dropna().index[-1] - index.dropna().index[0]).days / 365.25
    result = {
        "cagr": float((equity.iloc[-1] / CAPITAL) ** (1 / years) - 1),
        "max_drawdown": float((equity / equity.cummax() - 1).min()),
        "benchmark_cagr": float(
            (index.dropna().iloc[-1] / index.dropna().iloc[0]) ** (1 / benchmark_years) - 1
        ),
        "benchmark_max_drawdown": float((index / index.cummax() - 1).min()),
        "sharpe": float(daily.mean() / daily.std() * math.sqrt(252)),
        "win_rate": float(np.mean(np.array(trades) > 0)) if trades else None,
        "trades": len(trades),
    }
    for label, days in (("3m", 63), ("6m", 126), ("9m", 189), ("12m", 252)):
        rolling = equity.pct_change(days).dropna()
        result[label] = {
            "profitable": float((rolling > 0).mean()),
            "median": float(rolling.median()),
            "worst": float(rolling.min()),
        }
    return result


def main() -> None:
    symbols = json.loads((ROOT / "data/us_watchlist.json").read_text())
    with ThreadPoolExecutor(max_workers=8) as pool:
        datasets = list(pool.map(lambda symbol: yahoo_chart(symbol, "10y", "1d"), symbols))
    frames = {dataset.symbol: dataset.frame for dataset in datasets}
    benchmark = yahoo_chart("SPY", "10y", "1d").frame
    dates = pd.DatetimeIndex(benchmark.timestamp.dt.tz_localize(None)).normalize()
    start, split, end = dates.min(), dates.min() + pd.DateOffset(years=5), dates.max()
    output = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "currency": "USD",
        "benchmark": "SPY adjusted total-return proxy",
        "universe": "Fixed 31-stock liquid research shortlist",
        "survivorship_bias": True,
        "cost_bps_one_way": COST * 10_000,
        "development": simulate(frames, benchmark, start, split - pd.Timedelta(days=1)),
        "holdout": simulate(frames, benchmark, split, end),
    }
    path = ROOT / "artifacts/us_phase2_results.json"
    path.write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
