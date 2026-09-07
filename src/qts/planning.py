"""Shared completed-session momentum ranking and one target per security."""
from __future__ import annotations

import math

import pandas as pd

from qts.paper_broker import deterministic_id
from qts.research import rank_at, validate_inputs


def plan_targets(phase: str, settings: dict, state: dict, prices: pd.DataFrame,
                 membership: pd.DataFrame, execution_day: pd.Timestamp) -> dict:
    validate_inputs(prices, membership)
    scores = rank_at(prices, membership, execution_day, lookback=settings["lookback"],
                     min_history=settings["min_history"], min_price=settings["min_price"],
                     min_traded_value=settings["min_median_traded_value"])
    current = state.get("positions", {})
    selected = {s for s in current if s in scores.head(settings["keep_rank"]).index}
    for symbol in scores.index:
        if len(selected) >= settings["max_positions"]:
            break
        selected.add(symbol)
    if not len(scores):
        raise ValueError("No valid ranked universe; do not interpret data failure as sell-all")
    latest = prices[prices.date < execution_day].sort_values("date").groupby("security_id").last()
    if any(s not in latest.index for s in current):
        raise ValueError("Missing held-security history")
    equity = state["cash"] + sum(p["quantity"] * latest.loc[s, "raw_close"] for s, p in current.items())
    if not math.isfinite(equity) or equity <= 0:
        raise ValueError("Invalid marked equity")
    targets = {s: int(equity * settings["max_weight"] / (latest.loc[s, "raw_close"] * 1.0015)) for s in sorted(selected)}
    signal_at = latest.date.max().tz_localize("UTC") + pd.Timedelta(hours=23, minutes=59)
    return {"signal_id": deterministic_id(phase, signal_at.isoformat(), settings),
            "signal_at": signal_at.isoformat(), "targets": targets,
            "rankings": [{"security_id": s, "score": float(v), "rank": i + 1} for i, (s, v) in enumerate(scores.items())],
            "execution_rule": "next session open; execution risk gate rechecks current bid/ask and limits"}
