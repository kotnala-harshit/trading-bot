from __future__ import annotations

import io
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from qts.providers import yahoo_chart

ROOT = Path(__file__).resolve().parents[1]
CAPITAL = 1_000_000.0
COST = 0.0005
MEMBERSHIP_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/"
    "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"
)


def simulate(
    frames: dict[str, pd.DataFrame], benchmark: pd.DataFrame, start, end,
    membership: pd.Series | None = None, fx: pd.DataFrame | None = None,
    correlation_limit: float | None = None,
) -> dict:
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
    cash, positions, entries, trades, forced_exits, last_review = CAPITAL, {}, {}, [], 0, -60
    curve = []
    for day_number, day in enumerate(calendar):
        po, pc = opens.loc[day], close.loc[day]
        for symbol in [symbol for symbol in positions if pd.isna(po[symbol])]:
            prior = close.loc[close.index < day, symbol].dropna()
            price = float(prior.iloc[-1]) if not prior.empty else entries[symbol]
            cash += positions[symbol] * price * (1 - COST)
            trades.append(price / entries[symbol] - 1 - 2 * COST)
            del positions[symbol], entries[symbol]
            forced_exits += 1
        prices = {symbol: float(po[symbol]) for symbol in positions if pd.notna(po[symbol])}
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
            score = scores.loc[day].replace([np.inf, -np.inf], np.nan).dropna()
            if membership is not None:
                eligible = membership.asof(day)
                score = score[score.index.isin(eligible)]
            candidates = list(score.nlargest(30).index)
            ranked = []
            correlations = returns.loc[:day, candidates].tail(63).corr()
            for symbol in candidates:
                if correlation_limit is None or all(
                    abs(correlations.loc[symbol, held]) <= correlation_limit for held in ranked
                ):
                    ranked.append(symbol)
                if len(ranked) == 10:
                    break
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
    benchmark_equity = index / index.dropna().iloc[0] * CAPITAL
    if fx is not None:
        fx_close = fx.set_index(fx.timestamp.dt.tz_localize(None).dt.normalize()).close
        fx_close = fx_close.reindex(equity.index).ffill().bfill()
        equity_inr = equity * fx_close / fx_close.iloc[0]
        benchmark_inr = benchmark_equity.reindex(equity.index) * fx_close / fx_close.iloc[0]
    else:
        equity_inr, benchmark_inr = equity, benchmark_equity.reindex(equity.index)
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
        "inr_cagr": float((equity_inr.iloc[-1] / CAPITAL) ** (1 / years) - 1),
        "benchmark_inr_cagr": float((benchmark_inr.iloc[-1] / CAPITAL) ** (1 / years) - 1),
        "sharpe": float(daily.mean() / daily.std() * math.sqrt(252)),
        "win_rate": float(np.mean(np.array(trades) > 0)) if trades else None,
        "trades": len(trades),
        "forced_stale_exits": forced_exits,
    }
    for label, days in (("3m", 63), ("6m", 126), ("9m", 189), ("12m", 252)):
        rolling = equity.pct_change(days).dropna()
        benchmark_rolling = benchmark_equity.pct_change(days).reindex(rolling.index)
        result[label] = {
            "profitable": float((rolling > 0).mean()),
            "beat_benchmark": float((rolling > benchmark_rolling).mean()),
            "median": float(rolling.median()),
            "worst": float(rolling.min()),
        }
    return result


def load_membership() -> pd.Series:
    response = requests.get(MEMBERSHIP_URL, timeout=30)
    response.raise_for_status()
    history = pd.read_csv(io.StringIO(response.text), parse_dates=["date"])
    history["tickers"] = history.tickers.map(
        lambda value: frozenset(symbol.replace(".", "-") for symbol in value.split(","))
    )
    return history.set_index("date").tickers.sort_index()


def fetch(symbol: str):
    try:
        return yahoo_chart(symbol, "10y", "1d")
    except (OSError, ValueError, TypeError, KeyError, requests.RequestException):
        return None


def main() -> None:
    membership = load_membership()
    benchmark = yahoo_chart("SPY", "10y", "1d").frame
    dates = pd.DatetimeIndex(benchmark.timestamp.dt.tz_localize(None)).normalize()
    start, split, end = dates.min(), dates.min() + pd.DateOffset(years=5), dates.max()
    membership = membership[membership.index <= end]
    symbols = sorted(
        set(membership.asof(start)).union(*membership[membership.index >= start].tolist())
    )
    with ThreadPoolExecutor(max_workers=16) as pool:
        datasets = [dataset for dataset in pool.map(fetch, symbols) if dataset is not None]
    frames = {dataset.symbol: dataset.frame for dataset in datasets}
    fx = yahoo_chart("INR=X", "10y", "1d").frame
    development = simulate(
        frames, benchmark, start, split - pd.Timedelta(days=1), membership, fx
    )
    holdout = simulate(frames, benchmark, split, end, membership, fx)
    diversified_development = simulate(
        frames, benchmark, start, split - pd.Timedelta(days=1), membership, fx,
        correlation_limit=0.75,
    )
    diversified_holdout = simulate(
        frames, benchmark, split, end, membership, fx, correlation_limit=0.75
    )
    coverage = len(frames) / len(symbols)
    membership_current = membership.index.max() >= end - pd.Timedelta(days=7)
    withholding_modelled, holdout_reused = False, True
    promoted = (
        coverage >= 0.98
        and membership_current
        and withholding_modelled
        and not holdout_reused
        and holdout["cagr"] >= holdout["benchmark_cagr"] + 0.015
        and holdout["max_drawdown"] >= -0.20
        and holdout["12m"]["beat_benchmark"] >= 0.55
    )
    output = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "currency": "USD",
        "benchmark": "SPY adjusted total-return proxy",
        "universe": "Point-in-time community S&P 500 membership",
        "membership_source": MEMBERSHIP_URL,
        "membership_latest": membership.index.max().date().isoformat(),
        "membership_current": membership_current,
        "requested_symbols": len(symbols),
        "downloaded_symbols": len(frames),
        "price_coverage": coverage,
        "residual_survivorship_bias": coverage < 0.98,
        "withholding_rate": 0.25,
        "withholding_modelled": withholding_modelled,
        "holdout_reused_after_baseline_review": holdout_reused,
        "cost_bps_one_way": COST * 10_000,
        "promotion_passed": promoted,
        "correlation_experiment": {
            "status": "rejected",
            "limit": 0.75,
            "development": diversified_development,
            "holdout": diversified_holdout,
        },
        "development": development,
        "holdout": holdout,
    }
    path = ROOT / "artifacts/us_phase2_results.json"
    path.write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
