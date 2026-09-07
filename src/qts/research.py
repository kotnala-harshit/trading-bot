"""Offline next-open research on explicit, dated security IDs and membership."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

COST_STRESS = (0, 5, 10, 15, 20, 30, 50)
NEIGHBORS = ({}, {"positions": 7}, {"positions": 8}, {"positions": 10},
             {"lookback": 42}, {"lookback": 84}, {"review": 40}, {"review": 80})


def eligible_members(membership: pd.DataFrame, day: pd.Timestamp) -> set[str]:
    # Half-open effective intervals; publication time prevents announcement look-ahead.
    selected = membership[(membership.effective_from <= day) & (membership.effective_to > day)
                          & (membership.known_at <= day)]
    return set(selected.security_id)


def validate_inputs(prices: pd.DataFrame, membership: pd.DataFrame) -> None:
    required = {"date", "security_id", "open", "close", "raw_close", "traded_value", "quality_ok"}
    if not required.issubset(prices):
        raise ValueError(f"Missing normalized columns: {required - set(prices)}")
    if prices.duplicated(["date", "security_id"]).any():
        raise ValueError("Duplicate security/session")
    if not {"security_id", "effective_from", "effective_to", "known_at"}.issubset(membership):
        raise ValueError("Dated point-in-time membership required")
    if (membership.effective_from >= membership.effective_to).any():
        raise ValueError("Invalid membership interval")
    for _, group in membership.groupby("security_id"):
        group = group.sort_values("effective_from")
        if (group.effective_from.iloc[1:].to_numpy() < group.effective_to.iloc[:-1].to_numpy()).any():
            raise ValueError("Overlapping membership intervals")
    if not np.isfinite(prices[["open", "close", "raw_close", "traded_value"]]).all().all():
        raise ValueError("Nonfinite normalized data")
    if (prices[["open", "close", "raw_close"]] <= 0).any().any() or (prices.traded_value < 0).any():
        raise ValueError("Invalid normalized price/liquidity")


def rank_at(prices: pd.DataFrame, membership: pd.DataFrame, day: pd.Timestamp, *,
            lookback=63, min_history=252, min_price=50, min_traded_value=100_000_000) -> pd.Series:
    history = prices[prices.date < day]
    members = eligible_members(membership, day)
    scores = {}
    previous_day = history.date.max()
    for symbol, frame in history[history.security_id.isin(members)].groupby("security_id"):
        frame = frame.sort_values("date")
        if len(frame) < max(min_history, lookback + 1) or frame.date.iloc[-1] != previous_day:
            continue
        if not frame.quality_ok.tail(min_history).eq(True).all():
            continue
        if frame.raw_close.iloc[-1] < min_price or frame.traded_value.tail(60).median() < min_traded_value:
            continue
        returns = frame.close.pct_change(fill_method=None).tail(lookback)
        vol = returns.std() * np.sqrt(252)
        if np.isfinite(vol) and vol > 0:
            scores[symbol] = (frame.close.iloc[-1] / frame.close.iloc[-lookback - 1] - 1) / vol
    return pd.Series(scores, dtype=float).sort_index().sort_values(ascending=False, kind="stable")


def simulate(prices: pd.DataFrame, membership: pd.DataFrame, *, capital=1_000_000,
             positions=5, lookback=63, keep_rank=10, review=60, cost_bps=15,
             min_history=252, min_price=50, min_traded_value=100_000_000,
             start=None, end=None, emergency_dd=-0.20, cooldown_days=28) -> tuple[pd.DataFrame, list]:
    validate_inputs(prices, membership)
    if positions < 1 or review < 1 or not 0 <= cost_bps < 10000 or capital <= 0:
        raise ValueError("Invalid simulation parameters")
    days = sorted(prices.date.unique())
    days = [pd.Timestamp(d) for d in days if (start is None or d >= start) and (end is None or d <= end)]
    cash, holdings, trades, curve = capital, {}, [], []
    high, last_review, cooldown = capital, -review, None
    costs, turnover = 0.0, 0.0
    for i, day in enumerate(days):
        rows = prices[prices.date == day].set_index("security_id")
        if any(s not in rows.index or not rows.loc[s, "quality_ok"] for s in holdings):
            raise ValueError(f"Missing/invalid held security on {day}; delisting evidence required")
        equity_open = cash + sum(p["quantity"] * rows.loc[s, "open"] for s, p in holdings.items())
        due = i - last_review >= review
        target = set(holdings)
        stopped = equity_open / high - 1 <= emergency_dd
        if stopped:
            cooldown = day + pd.Timedelta(days=cooldown_days)
        if stopped or (cooldown is not None and day < cooldown):
            target = set()
            due = False
        elif due:
            ranked = rank_at(prices, membership, day, lookback=lookback, min_history=min_history,
                             min_price=min_price, min_traded_value=min_traded_value)
            target = {s for s in holdings if s in ranked.head(max(keep_rank, positions)).index}
            for symbol in ranked.index:
                if len(target) >= positions:
                    break
                target.add(symbol)
            last_review = i
        for symbol in sorted(set(holdings) - target):
            position = holdings.pop(symbol)
            notional = position["quantity"] * rows.loc[symbol, "open"]
            fee = notional * cost_bps / 10000
            cash += notional - fee
            costs += fee
            turnover += notional / capital
            trades.append({"symbol": symbol, "entry": position["day"].isoformat(), "exit": day.isoformat(),
                           "pnl": notional - fee - position["cost"]})
        if stopped:
            high = cash
        for symbol in sorted(target - set(holdings)):
            if symbol not in rows.index or not rows.loc[symbol, "quality_ok"]:
                raise ValueError("No executable next-open price")
            # Adjusted total-return units, not broker shares; fractional units avoid split artifacts.
            budget = min(equity_open / positions, cash)
            quantity = budget / (rows.loc[symbol, "open"] * (1 + cost_bps / 10000))
            notional = quantity * rows.loc[symbol, "open"]
            fee = notional * cost_bps / 10000
            cash -= notional + fee
            costs += fee
            turnover += notional / capital
            holdings[symbol] = {"quantity": quantity, "cost": notional + fee, "day": day}
        equity = cash + sum(p["quantity"] * rows.loc[s, "close"] for s, p in holdings.items())
        high = max(high, equity)
        curve.append({"date": day, "equity": equity, "cash": cash, "costs": costs, "turnover": turnover,
                      "holdings": ",".join(sorted(holdings))})
    if not curve:
        raise ValueError("No research sessions")
    return pd.DataFrame(curve).set_index("date"), trades


def statistics(curve: pd.DataFrame, trades: list, capital: float) -> dict:
    equity = curve.equity
    returns = equity.pct_change().fillna(equity.iloc[0] / capital - 1)
    years = max((curve.index[-1] - curve.index[0]).days / 365.25, 1 / 252)
    growth = equity.iloc[-1] / capital
    high = equity.cummax().clip(lower=capital)
    dd = equity / high - 1
    volatility = returns.std() * np.sqrt(252)
    downside = np.sqrt((returns.clip(upper=0) ** 2).mean()) * np.sqrt(252)
    pnl = np.array([t["pnl"] for t in trades])
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    monthly = equity.resample("ME").last().pct_change().dropna()
    yearly = equity.resample("YE").last().pct_change().dropna()
    duration = longest = 0
    for value in dd:
        duration = duration + 1 if value < 0 else 0
        longest = max(longest, duration)
    cagr = growth ** (1 / years) - 1 if years >= 1 else None
    output = {"starting_capital": capital, "ending_capital": equity.iloc[-1], "total_return": growth - 1,
              "cagr": cagr, "max_drawdown": dd.min(), "average_drawdown": dd.mean(),
              "drawdown_duration_sessions": longest, "volatility": volatility,
              "sharpe": returns.mean() * 252 / volatility if volatility else None,
              "sortino": returns.mean() * 252 / downside if downside else None,
              "calmar": cagr / abs(dd.min()) if cagr is not None and dd.min() < 0 else None,
              "trades": len(trades), "wins": len(wins), "losses": len(losses),
              "win_rate": len(wins) / len(pnl) if len(pnl) else None,
              "average_winner": wins.mean() if len(wins) else None,
              "average_loser": losses.mean() if len(losses) else None,
              "largest_winner": wins.max() if len(wins) else None,
              "largest_loser": losses.min() if len(losses) else None,
              "profit_factor": wins.sum() / abs(losses.sum()) if len(losses) else None,
              "expectancy": pnl.mean() if len(pnl) else None,
              "turnover": curve.turnover.iloc[-1], "combined_execution_cost": curve.costs.iloc[-1],
              "positive_months": int((monthly > 0).sum()), "positive_years": int((yearly > 0).sum()),
              "best_month": monthly.max() if len(monthly) else None,
              "worst_month": monthly.min() if len(monthly) else None,
              "best_year": yearly.max() if len(yearly) else None, "worst_year": yearly.min() if len(yearly) else None,
              "taxes": None, "fees": None, "spread": None, "slippage": None}
    return {k: float(v) if isinstance(v, np.floating) and np.isfinite(v) else None if isinstance(v, np.floating) else v for k, v in output.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--membership", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=["india", "us", "global"], required=True)
    parser.add_argument("--development-end", required=True)
    parser.add_argument("--validation-end", required=True)
    args = parser.parse_args()
    prices = pd.read_csv(args.prices, parse_dates=["date"])
    members = pd.read_csv(args.membership, parse_dates=["effective_from", "effective_to", "known_at"])
    benchmark = pd.read_csv(args.benchmark, parse_dates=["date"]).set_index("date")
    config = json.loads((Path(__file__).resolve().parents[2] / "configs/phases.json").read_text())[args.phase]
    kwargs = {"capital": config["capital"], "min_history": config["min_history"], "min_price": config["min_price"], "min_traded_value": config["min_median_traded_value"]}
    dev, val = pd.Timestamp(args.development_end), pd.Timestamp(args.validation_end)
    if not prices.date.min() < dev < val < prices.date.max():
        raise ValueError("Require chronological development < validation < holdout")
    sessions = sorted(prices.date.unique())
    research_start = pd.Timestamp(sessions[config["min_history"]])
    def report(curve, trades, capital):
        stats = statistics(curve, trades, capital)
        reference = benchmark.reindex(curve.index)
        if reference[["open", "close"]].isna().any().any():
            raise ValueError("Missing benchmark sessions")
        growth = reference.close.iloc[-1] / reference.open.iloc[0]
        years = (curve.index[-1] - curve.index[0]).days / 365.25
        stats.update(benchmark_total_return=float(growth - 1),
                     benchmark_cagr=float(growth ** (1 / years) - 1) if years >= 1 else None,
                     excess_return=float(stats["total_return"] - (growth - 1)))
        return stats
    windows = {"development": (research_start, dev), "validation": (dev + pd.Timedelta(days=1), val),
               "holdout_already_opened_not_blind": (val + pd.Timedelta(days=1), None), "full": (research_start, None)}
    output = {"status": "RESEARCH ONLY; no automatic promotion", "data_sha256": hashlib.sha256(args.prices.read_bytes()).hexdigest(),
              "membership_sha256": hashlib.sha256(args.membership.read_bytes()).hexdigest(), "windows": {}, "cost_stress": {}, "nearby_development_only": []}
    for label, (start, end) in windows.items():
        curve, trades = simulate(prices, members, start=start, end=end, **kwargs)
        output["windows"][label] = report(curve, trades, config["capital"])
    for bps in COST_STRESS:
        curve, trades = simulate(prices, members, cost_bps=bps, start=research_start, **kwargs)
        output["cost_stress"][bps] = report(curve, trades, config["capital"])
    for params in NEIGHBORS:
        curve, trades = simulate(prices, members, start=research_start, end=dev, **params, **kwargs)
        output["nearby_development_only"].append({"parameters": params, "results": report(curve, trades, config["capital"])})
    full, full_trades = simulate(prices, members, start=research_start, **kwargs)
    output["rolling"] = {}
    for months in (3, 6, 12, 36, 60):
        results = []
        for endpoint in full.resample("QE").last().index:
            start = endpoint - pd.DateOffset(months=months)
            if start < full.index[0] or endpoint > full.index[-1]:
                continue
            window = full.loc[(full.index > start) & (full.index <= endpoint)].copy()
            prior = full.loc[full.index <= start].iloc[-1]
            window["costs"] -= prior.costs
            window["turnover"] -= prior.turnover
            closed = [t for t in full_trades if start < pd.Timestamp(t["exit"]) <= endpoint]
            stats = report(window, closed, float(prior.equity))
            stats["end"] = endpoint.isoformat()
            results.append(stats)
        output["rolling"][f"{months}m"] = results
    output["walk_forward_fixed_baseline"] = []
    start = dev + pd.Timedelta(days=1)
    while start < prices.date.max():
        end = min(start + pd.DateOffset(years=1) - pd.Timedelta(days=1), prices.date.max())
        curve, trades = simulate(prices, members, start=start, end=end, **kwargs)
        output["walk_forward_fixed_baseline"].append({"start": start.isoformat(), "end": end.isoformat(),
                                                      "metrics": report(curve, trades, config["capital"])})
        start = end + pd.Timedelta(days=1)
    output["methodology"] = "Fixed baseline, no holdout parameter selection. Rolling trade P&L includes full closed-trade life. Zero-bps run is gross comparator; taxes and component costs unmeasured. Current ETF universes are diagnostic only."
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
