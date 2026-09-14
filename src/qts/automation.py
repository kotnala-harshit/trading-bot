from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "runtime" / "paper_state.json"
LEDGER_PATH = ROOT / "runtime" / "paper_ledger.csv"
WATCHLIST_PATH = ROOT / "data" / "indian_watchlist.json"
CONTROL_PATH = ROOT / "configs" / "paper-trader.json"
PAGE_PATH = ROOT / "docs" / "index.html"
US_RESULTS_PATH = ROOT / "artifacts" / "us_phase2_results.json"
US_STATE_PATH = ROOT / "runtime" / "us_paper_state.json"
US_ETF_RESULTS_PATH = ROOT / "artifacts" / "us_phase2_etf_results.json"
STARTING_CAPITAL = 1_000_000.0
MAX_POSITIONS = 5
KEEP_RANK = 10
REVIEW_SESSIONS = 60
FEE_BPS = 10.0
MAX_DRAWDOWN = -0.20
COOLDOWN_DAYS = 28


def market_is_open(now: datetime | None = None) -> bool:
    india = (now or datetime.now(UTC)).astimezone(ZoneInfo("Asia/Kolkata"))
    minutes = india.hour * 60 + india.minute
    return india.weekday() < 5 and 9 * 60 + 15 <= minutes <= 15 * 60 + 30


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {
        "cash": STARTING_CAPITAL,
        "positions": {},
        "peak_equity": STARTING_CAPITAL,
        "last_equity": STARTING_CAPITAL,
        "last_run": None,
        "cooldown_until": None,
        "last_scan_date": None,
        "sessions_since_review": REVIEW_SESSIONS,
        "status": "Waiting for first scheduled market-hours run",
    }


def cooldown_active(state: dict, now: datetime) -> bool:
    value = state.get("cooldown_until")
    return bool(value and now < datetime.fromisoformat(value))


def drawdown_stop_triggered(drawdown: float, has_positions: bool) -> bool:
    return has_positions and drawdown <= MAX_DRAWDOWN


def quote_is_current(latest_timestamp, india_day: str) -> bool:
    return latest_timestamp.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat() == india_day


def trading_enabled() -> bool:
    return bool(json.loads(CONTROL_PATH.read_text()).get("enabled", False))


def append_fills(fills: list) -> None:
    if not fills:
        return
    exists = LEDGER_PATH.exists()
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("a", newline="") as handle:
        writer = csv.writer(handle)
        if not exists:
            writer.writerow(["timestamp", "symbol", "side", "quantity", "price", "fees"])
        for fill in fills:
            writer.writerow(
                [fill.timestamp, fill.symbol, fill.side, fill.quantity, fill.price, fill.fees]
            )


def record_history(state: dict, timestamp: str, nifty: float) -> None:
    history = state.setdefault("equity_history", [])
    history.append({"timestamp": timestamp, "equity": state["last_equity"], "nifty": nifty})
    state["equity_history"] = history[-5000:]


def fyers_symbol(symbol: str) -> str:
    return f"NSE:{symbol.removesuffix('.NS')}-EQ"


def record_observation(state: dict, now: datetime) -> dict:
    """Record FYERS marks only; this path does not create or transmit orders."""
    from qts.fyers import get_depth

    india_day = now.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()
    quotes = {}
    try:
        for symbol, position in state.get("positions", {}).items():
            quote = get_depth(fyers_symbol(symbol), symbol)
            if not quote_is_current(datetime.fromisoformat(quote.timestamp), india_day):
                raise ValueError(f"stale FYERS quote for {symbol}")
            quotes[symbol] = quote
            position["last_price"] = quote.last
        nifty = get_depth("NSE:NIFTY50-INDEX", "NIFTY50")
        if not quote_is_current(datetime.fromisoformat(nifty.timestamp), india_day):
            raise ValueError("stale FYERS quote for Nifty 50")
    except (OSError, ValueError, requests.RequestException) as error:
        state["status"] = f"India observation skipped: {error}; no orders"
        return state
    equity = state["cash"] + sum(position["quantity"] * quotes[symbol].last for symbol, position in state.get("positions", {}).items())
    state["last_equity"] = equity
    state["peak_equity"] = max(state.get("peak_equity", equity), equity)
    record_history(state, now.isoformat(), nifty.last)
    state["last_successful_scan"] = now.isoformat()
    state["latest_data_at"] = min([quote.timestamp for quote in quotes.values()] + [nifty.timestamp])
    state["status"] = "India observation recorded from FYERS market data; no orders"
    return state


def render_page(state: dict, quotes: dict[str, float]) -> None:
    from qts.dashboard import render_dashboard
    render_dashboard(ROOT, PAGE_PATH, india_state=state, quotes=quotes)


def run(force: bool = False) -> dict:
    now = datetime.now(UTC)
    state = load_state()
    state["last_attempt"] = now.isoformat()
    if force or market_is_open(now):
        record_observation(state, now)
    else:
        state["status"] = "NSE market closed; no observation or orders"
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))
    render_page(state, {})
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Run outside NSE hours for testing")
    args = parser.parse_args()
    print(json.dumps(run(force=args.force), indent=2))


if __name__ == "__main__":
    main()
