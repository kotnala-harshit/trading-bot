from __future__ import annotations

import argparse
import csv
import io
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

from qts.paper import execute_paper_fill, mark_to_market
from qts.providers import yahoo_chart
from qts.strategy import risk_adjusted_momentum_score

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "runtime" / "us_paper_state.json"
LEDGER_PATH = ROOT / "runtime" / "us_paper_ledger.csv"
CONTROL_PATH = ROOT / "configs" / "paper-trader.json"
MEMBERSHIP_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/"
    "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"
)
CAPITAL, MAX_POSITIONS, KEEP_RANK, REVIEW_SESSIONS = 10_000.0, 5, 15, 120
FEE_BPS, TARGET_VOL, MAX_EXPOSURE = 5.0, 0.07, 0.40


def us_market_is_open(now: datetime | None = None) -> bool:
    local = (now or datetime.now(UTC)).astimezone(ZoneInfo("America/New_York"))
    minutes = local.hour * 60 + local.minute
    return local.weekday() < 5 and 9 * 60 + 30 <= minutes <= 16 * 60


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {
        "cash": CAPITAL,
        "positions": {},
        "peak_equity": CAPITAL,
        "last_equity": CAPITAL,
        "sessions_since_review": REVIEW_SESSIONS,
        "status": "Waiting for first US market-hours paper run",
    }


def save(state: dict, fills=()) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))
    if not fills:
        return
    exists = LEDGER_PATH.exists()
    with LEDGER_PATH.open("a", newline="") as handle:
        writer = csv.writer(handle)
        if not exists:
            writer.writerow(["timestamp", "symbol", "side", "quantity", "price", "fees"])
        for fill in fills:
            writer.writerow(
                [fill.timestamp, fill.symbol, fill.side, fill.quantity, fill.price, fill.fees]
            )


def current_members() -> list[str]:
    response = requests.get(MEMBERSHIP_URL, timeout=30)
    response.raise_for_status()
    history = pd.read_csv(io.StringIO(response.text))
    return sorted(symbol.replace(".", "-") for symbol in history.iloc[-1].tickers.split(","))


def fetch(symbol: str, review: bool):
    try:
        return yahoo_chart(symbol, "5y" if review else "1d", "1d" if review else "5m")
    except (OSError, ValueError, TypeError, KeyError, requests.RequestException):
        return None


def exposure(spy: pd.DataFrame) -> float:
    if len(spy) < 201 or spy.close.iloc[-1] <= spy.close.ewm(span=200).mean().iloc[-1]:
        return 0.0
    volatility = float(spy.close.pct_change().tail(20).std() * math.sqrt(252))
    return min(MAX_EXPOSURE, TARGET_VOL / volatility) if np.isfinite(volatility) and volatility > 0 else 0.0


def run(force: bool = False) -> dict:
    from qts.automation import load_state as load_india_state
    from qts.automation import render_page

    state, now = load_state(), datetime.now(UTC)
    state["last_attempt"] = now.isoformat()
    control = json.loads(CONTROL_PATH.read_text())
    if not control.get("us_enabled", False) or (not force and not us_market_is_open(now)):
        state["status"] = "US paper disabled" if not control.get("us_enabled") else "US market closed"
        save(state)
        render_page(load_india_state(), {})
        return state

    day = now.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    try:
        spy = yahoo_chart("SPY", "1y", "1d").frame
        target = exposure(spy)
    except (OSError, ValueError, TypeError, KeyError, requests.RequestException):
        state["status"] = "Skipped: SPY risk data unavailable"
        save(state)
        return state

    new_session = state.get("last_scan_date") != day
    sessions = state.get("sessions_since_review", REVIEW_SESSIONS) + int(new_session)
    review = not state["positions"] or sessions >= REVIEW_SESSIONS
    symbols = current_members() if review else list(state["positions"])
    with ThreadPoolExecutor(max_workers=16) as pool:
        datasets = [item for item in pool.map(lambda symbol: fetch(symbol, review), symbols) if item]
    candidates, quotes = [], {}
    for dataset in datasets:
        frame = dataset.frame
        if frame.timestamp.iloc[-1].tz_convert(ZoneInfo("America/New_York")).date().isoformat() != day:
            continue
        price = float(frame.close.iloc[-1])
        quotes[dataset.symbol] = price
        score = risk_adjusted_momentum_score(frame) if review else None
        if score is not None:
            candidates.append((score, dataset.symbol, price))
    if (review and len(candidates) < 350) or (not review and len(quotes) < len(symbols)):
        state["status"] = f"Skipped: only {len(candidates) if review else len(quotes)} valid US quotes"
        save(state)
        render_page(load_india_state(), {})
        return state

    state.update(last_scan_date=day, sessions_since_review=sessions, exposure_target=target)
    equity = state["cash"] + sum(
        item["quantity"] * quotes.get(symbol, item["last_price"])
        for symbol, item in state["positions"].items()
    )
    state["peak_equity"] = max(state.get("peak_equity", equity), equity)
    fills, ranked = [], sorted(candidates, reverse=True)
    allowed = {symbol for _, symbol, _ in ranked[:KEEP_RANK]} if target else set()
    for symbol in list(state["positions"]):
        item, price = state["positions"][symbol], quotes[symbol]
        if target == 0 or (review and symbol not in allowed):
            state["cash"], _, fill = execute_paper_fill(
                state["cash"], item["quantity"], symbol=symbol, side="SELL",
                quantity=item["quantity"], price=price, fee_bps=FEE_BPS,
            )
            fills.append(fill)
            del state["positions"][symbol]
    target_value = equity * target / MAX_POSITIONS
    if review and target:
        state["sessions_since_review"] = 0
        for _, symbol, price in ranked:
            if symbol in state["positions"] or len(state["positions"]) >= MAX_POSITIONS:
                continue
            quantity = min(int(target_value / price), int(state["cash"] / (price * 1.0005)))
            if quantity:
                state["cash"], _, fill = execute_paper_fill(
                    state["cash"], 0, symbol=symbol, side="BUY", quantity=quantity,
                    price=price, fee_bps=FEE_BPS,
                )
                fills.append(fill)
                state["positions"][symbol] = {
                    "quantity": quantity, "entry_price": price, "last_price": price,
                    "opened_at": now.isoformat(),
                }
    for symbol, item in state["positions"].items():
        item["last_price"] = quotes[symbol]
    state["last_equity"] = state["cash"] + sum(
        mark_to_market(0, item["quantity"], item["last_price"])
        for item in state["positions"].values()
    )
    state["last_run"] = state["last_successful_scan"] = now.isoformat()
    state["status"] = f"US paper {'review' if review else 'monitor'}; {len(fills)} fill(s); {target:.0%} exposure"
    save(state, fills)
    render_page(load_india_state(), {})
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    print(json.dumps(run(parser.parse_args().force), indent=2))


if __name__ == "__main__":
    main()
