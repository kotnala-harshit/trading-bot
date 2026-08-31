from __future__ import annotations

import argparse
import csv
import html
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from qts.paper import execute_paper_fill, mark_to_market
from qts.providers import yahoo_chart
from qts.risk_plan import size_long_position
from qts.strategy import candidate_score, market_regime_is_positive

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "runtime" / "paper_state.json"
LEDGER_PATH = ROOT / "runtime" / "paper_ledger.csv"
WATCHLIST_PATH = ROOT / "data" / "indian_watchlist.json"
PAGE_PATH = ROOT / "docs" / "index.html"
STARTING_CAPITAL = 1_000_000.0
MAX_POSITIONS = 6
FEE_BPS = 10.0


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
        "status": "Waiting for first scheduled market-hours run",
    }


def cooldown_active(state: dict, now: datetime) -> bool:
    value = state.get("cooldown_until")
    return bool(value and now < datetime.fromisoformat(value))


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


def render_page(state: dict, quotes: dict[str, float]) -> None:
    positions = []
    for symbol, item in state["positions"].items():
        price = quotes.get(symbol, item.get("last_price", item["entry_price"]))
        value = item["quantity"] * price
        pnl = value - item["quantity"] * item["entry_price"]
        positions.append(
            f"<tr><td>{html.escape(symbol)}</td><td>{item['quantity']}</td>"
            f"<td>₹{item['entry_price']:,.2f}</td><td>₹{price:,.2f}</td>"
            f"<td>₹{value:,.2f}</td><td>₹{pnl:,.2f}</td></tr>"
        )
    rows = "".join(positions) or "<tr><td colspan='6'>No open paper positions</td></tr>"
    page = f"""<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Indian Equity Paper Trader</title><style>
body{{font:16px system-ui;max-width:1000px;margin:40px auto;padding:0 18px;color:#18202a}}
.cards{{display:flex;gap:14px;flex-wrap:wrap}}.card{{padding:18px;background:#f2f6fa;border-radius:12px;min-width:180px}}
table{{border-collapse:collapse;width:100%;margin-top:22px}}th,td{{padding:10px;border-bottom:1px solid #ddd;text-align:right}}th:first-child,td:first-child{{text-align:left}}
.safe{{color:#087f5b}}.warning{{background:#fff3bf;padding:12px;border-radius:8px}}</style></head><body>
<h1>Indian Equity Paper Trader</h1>
<p class='safe'><strong>PAPER ONLY · REAL ORDERS DISABLED</strong></p>
<div class='cards'><div class='card'>Equity<br><strong>₹{state['last_equity']:,.2f}</strong></div>
<div class='card'>Cash<br><strong>₹{state['cash']:,.2f}</strong></div>
<div class='card'>Positions<br><strong>{len(state['positions'])}/{MAX_POSITIONS}</strong></div></div>
<p><strong>Status:</strong> {html.escape(state['status'])}<br><strong>Last run:</strong> {state['last_run'] or 'Not run yet'}</p>
<table><thead><tr><th>Symbol</th><th>Shares</th><th>Entry</th><th>Latest</th><th>Value</th><th>Open P/L</th></tr></thead><tbody>{rows}</tbody></table>
<p class='warning'>Delayed public data and GitHub schedules are not exchange-grade. Results include estimated costs but not taxes, gaps, or guaranteed fills.</p>
</body></html>"""
    PAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAGE_PATH.write_text(page)


def run(force: bool = False) -> dict:
    state = load_state()
    now = datetime.now(UTC)
    if not force and not market_is_open(now):
        state["status"] = "Skipped: NSE market is closed"
        state["last_run"] = now.isoformat()
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))
        render_page(state, {})
        return state

    watchlist = json.loads(WATCHLIST_PATH.read_text())
    candidates, quotes = [], {}
    try:
        index_frame = yahoo_chart("^NSEI", period="5y", interval="1d").frame
        positive_regime = market_regime_is_positive(index_frame)
    except (OSError, ValueError, TypeError, KeyError, IndexError, requests.RequestException):
        positive_regime = False
    for symbol in watchlist:
        try:
            frame = yahoo_chart(symbol, period="5y", interval="1d").frame
            price = float(frame.close.iloc[-1])
            quotes[symbol] = price
            score = candidate_score(frame)
            if positive_regime and score is not None:
                candidates.append((score, symbol, price))
        except (OSError, ValueError, TypeError, KeyError, IndexError, requests.RequestException):
            continue

    fills = []
    equity = state["cash"] + sum(
        item["quantity"] * quotes.get(symbol, item.get("last_price", item["entry_price"]))
        for symbol, item in state["positions"].items()
    )
    state["peak_equity"] = max(state.get("peak_equity", equity), equity)
    drawdown = equity / state["peak_equity"] - 1
    if state.get("cooldown_until") and not cooldown_active(state, now):
        state["cooldown_until"] = None
        state["peak_equity"] = equity
    allowed = {symbol for _, symbol, _ in sorted(candidates, reverse=True)[:MAX_POSITIONS]}
    drawdown_stop = drawdown <= -0.05 and bool(state["positions"])
    if drawdown_stop:
        state["cooldown_until"] = (now + timedelta(days=28)).isoformat()
    if drawdown_stop or cooldown_active(state, now):
        allowed.clear()

    for symbol in list(state["positions"]):
        item = state["positions"][symbol]
        price = quotes.get(symbol, item.get("last_price", item["entry_price"]))
        if symbol not in allowed or price <= item["entry_price"] * 0.95:
            state["cash"], _, fill = execute_paper_fill(
                state["cash"], item["quantity"], symbol=symbol, side="SELL",
                quantity=item["quantity"], price=price, fee_bps=FEE_BPS,
            )
            fills.append(fill)
            del state["positions"][symbol]
    if drawdown_stop:
        state["peak_equity"] = state["cash"]

    for _, symbol, price in sorted(candidates, reverse=True):
        if symbol in state["positions"] or len(state["positions"]) >= MAX_POSITIONS:
            continue
        plan = size_long_position(equity, price, stop_pct=0.05)
        affordable = int(state["cash"] / (price * (1 + FEE_BPS / 10_000)))
        quantity = min(plan.shares, affordable)
        if quantity < 1:
            continue
        state["cash"], _, fill = execute_paper_fill(
            state["cash"], 0, symbol=symbol, side="BUY", quantity=quantity,
            price=price, fee_bps=FEE_BPS,
        )
        fills.append(fill)
        state["positions"][symbol] = {
            "quantity": quantity, "entry_price": price, "last_price": price
        }

    for symbol, item in state["positions"].items():
        item["last_price"] = quotes.get(symbol, item.get("last_price", item["entry_price"]))
    state["last_equity"] = state["cash"] + sum(
        mark_to_market(0, item["quantity"], item["last_price"])
        for item in state["positions"].values()
    )
    state["last_run"] = now.isoformat()
    regime = "positive" if positive_regime else "defensive/cash"
    state["status"] = f"Completed scan; market regime {regime}; {len(fills)} fill(s)"
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))
    append_fills(fills)
    render_page(state, quotes)
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Run outside NSE hours for testing")
    args = parser.parse_args()
    print(json.dumps(run(force=args.force), indent=2))


if __name__ == "__main__":
    main()
