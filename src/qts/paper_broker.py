"""Durable, long-only paper execution. No network or real-order endpoint."""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from qts.broker import Quote
from qts.execution import build_rebalance_orders, executable_price


def deterministic_id(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, allow_nan=False).encode()).hexdigest()[:32]


def validate_quote(quote: Quote, now: datetime, max_age: float = 60) -> None:
    if not quote.symbol or not quote.timestamp or quote.provider == "unknown":
        raise ValueError("Quote identity, provider and exchange timestamp required")
    stamp = datetime.fromisoformat(quote.timestamp)
    if stamp.tzinfo is None or now.tzinfo is None or not 0 <= (now - stamp).total_seconds() <= max_age:
        raise ValueError(f"Stale/future quote: {quote.symbol}")
    if any(v is None or not math.isfinite(v) or v <= 0 for v in (quote.last, quote.bid, quote.ask)):
        raise ValueError(f"Invalid/missing bid/ask: {quote.symbol}")
    if quote.bid > quote.ask:
        raise ValueError(f"Crossed quote: {quote.symbol}")
    for size in (quote.bid_size, quote.ask_size):
        if type(size) is not int or size <= 0:
            raise ValueError(f"Missing executable liquidity: {quote.symbol}")


def validate_pair(primary: Quote, secondary: Quote, now: datetime,
                  max_age: float = 60, max_divergence_bps: float = 30) -> None:
    for quote in (primary, secondary):
        validate_quote(quote, now, max_age)
    if primary.symbol != secondary.symbol or primary.provider == secondary.provider:
        raise ValueError("Validation requires matching security identities and independent providers")
    first, second = (primary.bid + primary.ask) / 2, (secondary.bid + secondary.ask) / 2
    if abs(first / second - 1) * 10_000 > max_divergence_bps:
        raise ValueError("Provider price divergence")


class PaperBroker:
    def __init__(self, path: str | Path, phase: str, capital: float):
        if phase not in {"india", "us", "global"} or not math.isfinite(capital) or capital <= 0:
            raise ValueError("Invalid phase/capital")
        self.phase, self.capital = phase, capital
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30)
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS accounts(phase TEXT PRIMARY KEY, opening TEXT, state TEXT);
            CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, phase TEXT, intent TEXT, result TEXT);
            CREATE TABLE IF NOT EXISTS fills(id TEXT PRIMARY KEY, phase TEXT, payload TEXT);
        ''')
        opening = json.dumps({"cash": capital, "positions": {}, "realized_pnl": 0.0, "fees": 0.0})
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO accounts VALUES(?,?,?)", (phase, opening, opening))
        actual = json.loads(self.db.execute("SELECT opening FROM accounts WHERE phase=?", (phase,)).fetchone()[0])
        if actual["cash"] != capital:
            raise ValueError("Starting capital differs from persisted account")

    def close(self):
        self.db.close()

    def state(self) -> dict:
        return json.loads(self.db.execute("SELECT state FROM accounts WHERE phase=?", (self.phase,)).fetchone()[0])

    def reconciliation(self) -> dict:
        opening = json.loads(self.db.execute("SELECT opening FROM accounts WHERE phase=?", (self.phase,)).fetchone()[0])
        cash, positions = opening["cash"], {}
        for (payload,) in self.db.execute("SELECT payload FROM fills WHERE phase=? ORDER BY rowid", (self.phase,)):
            fill = json.loads(payload)
            sign = 1 if fill["side"] == "BUY" else -1
            cash -= sign * fill["quantity"] * fill["price"] + fill["fees"]
            positions[fill["symbol"]] = positions.get(fill["symbol"], 0) + sign * fill["quantity"]
        actual = self.state()
        expected = {s: p["quantity"] for s, p in actual["positions"].items() if p["quantity"]}
        positions = {s: q for s, q in positions.items() if q}
        difference = actual["cash"] - cash
        return {"matched": expected == positions and abs(difference) < 0.000001,
                "cash_difference": difference, "ledger_positions": positions,
                "account_positions": expected, "scope": "internal paper ledger vs account"}

    def rebalance(self, signal_id: str, targets: dict[str, int], quotes: dict[str, Quote],
                  validators: dict[str, Quote], *, now: datetime | None = None,
                  transmit_orders: bool = False, fee_bps: float = 10, slippage_bps: float = 5,
                  max_positions: int = 5, max_weight: float = 0.20,
                  max_age: float = 60, max_divergence_bps: float = 30,
                  emergency_dd: float = -0.20, cooldown_days: int = 28) -> dict:
        if transmit_orders is not False:
            raise PermissionError("Real order transmission is disabled")
        if not signal_id or any(type(q) is not int or q < 0 for q in targets.values()):
            raise ValueError("Stable signal ID and nonnegative integer targets required")
        if any(not math.isfinite(x) or not 0 <= x < 10000 for x in (fee_bps, slippage_bps)):
            raise ValueError("Invalid execution costs")
        if max_positions < 1 or not 0 < max_weight <= 1 or max_age <= 0 or max_divergence_bps < 0:
            raise ValueError("Invalid risk limits")
        now = now or datetime.now(UTC)
        batch_id = deterministic_id(self.phase, signal_id)
        intent = json.dumps(targets, sort_keys=True)
        # ponytail: one SQLite writer; move to a server DB for multiple execution hosts.
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            previous = self.db.execute("SELECT intent,result FROM batches WHERE id=?", (batch_id,)).fetchone()
            if previous:
                if previous[0] != intent:
                    raise ValueError("Signal ID reused with different targets")
                return json.loads(previous[1])
            state = self.state()
            result = {"rebalance_id": batch_id, "signal_id": signal_id, "phase": self.phase,
                      "timestamp": now.isoformat(), "orders": [], "reconciliation": self.reconciliation()}
            current = {s: p["quantity"] for s, p in state["positions"].items()}
            orders = build_rebalance_orders(current, targets)
            try:
                if not result["reconciliation"]["matched"]:
                    raise ValueError("Reconciliation failed; new orders blocked")
                if sum(q > 0 for q in targets.values()) > max_positions:
                    raise ValueError("Position count limit")
                for symbol in set(current) | {s for s, q in targets.items() if q}:
                    validate_pair(quotes[symbol], validators[symbol], now, max_age, max_divergence_bps)
                    if quotes[symbol].symbol != symbol:
                        raise ValueError("Quote key does not match security identity")
                equity = state["cash"] + sum(q * quotes[s].last for s, q in current.items())
                peak = max(state.get("peak_equity", self.capital), equity)
                state["peak_equity"] = peak
                cooldown = state.get("cooldown_until")
                if equity / peak - 1 <= emergency_dd:
                    state["cooldown_until"] = (now + timedelta(days=cooldown_days)).isoformat()
                    cooldown = state["cooldown_until"]
                if cooldown and now < datetime.fromisoformat(cooldown) and any(targets.values()):
                    raise ValueError("Drawdown/cooldown active; only liquidation target permitted")
                if cooldown and now >= datetime.fromisoformat(cooldown):
                    state["cooldown_until"] = None
                    state["peak_equity"] = equity
                if equity <= 0 or any(q * quotes[s].last > equity * max_weight + 1e-8
                                     for s, q in targets.items() if q):
                    raise ValueError("Position weight limit")
                if sum(q * quotes[s].last for s, q in targets.items() if q) > equity:
                    raise ValueError("Gross exposure exceeds equity")
            except (KeyError, ValueError, TypeError) as exc:
                result.update(status="REJECTED", error=str(exc))
                for order in orders:
                    result["orders"].append({**asdict(order), "order_id": deterministic_id(batch_id, order.symbol),
                                             "status": "REJECTED", "events": ["CREATED", "REJECTED"]})
            else:
                for order in orders:
                    oid = deterministic_id(batch_id, order.symbol)
                    quote = quotes[order.symbol]
                    price = executable_price(quote, order.side, slippage_bps)
                    capacity = quote.ask_size if order.side == "BUY" else quote.bid_size
                    quantity = min(order.quantity, capacity)
                    if order.side == "BUY" and order.symbol not in state["positions"] and len(state["positions"]) >= max_positions:
                        quantity = 0
                    if order.side == "BUY":
                        quantity = min(quantity, int(state["cash"] / (price * (1 + fee_bps / 10000))))
                    item = {**asdict(order), "order_id": oid, "filled_quantity": quantity,
                            "events": ["CREATED", "SUBMITTED", "ACKNOWLEDGED"]}
                    if quantity:
                        position = state["positions"].setdefault(order.symbol, {"quantity": 0, "entry_price": 0.0})
                        old = position["quantity"]
                        fees = quantity * price * fee_bps / 10000
                        sign = 1 if order.side == "BUY" else -1
                        state["cash"] -= sign * quantity * price + fees
                        state["fees"] += fees
                        if sign == 1:
                            position["entry_fees"] = position.get("entry_fees", 0.0) + fees
                            position["entry_price"] = (old * position["entry_price"] + quantity * price) / (old + quantity)
                        else:
                            entry_fees = position.get("entry_fees", 0.0) * quantity / old
                            state["realized_pnl"] += quantity * (price - position["entry_price"]) - fees - entry_fees
                            position["entry_fees"] = position.get("entry_fees", 0.0) - entry_fees
                        position["quantity"] += sign * quantity
                        if not position["quantity"]:
                            del state["positions"][order.symbol]
                        fill = {"fill_id": deterministic_id(oid, 0), "order_id": oid,
                                "rebalance_id": batch_id, "signal_id": signal_id, "timestamp": now.isoformat(),
                                "symbol": order.symbol, "side": order.side, "quantity": quantity,
                                "price": price, "fees": fees,
                                "spread_cost": quantity * abs((quote.ask if sign == 1 else quote.bid) - (quote.ask + quote.bid) / 2),
                                "slippage": quantity * abs(price - (quote.ask if sign == 1 else quote.bid)),
                                "implementation_shortfall": sign * quantity * (price - quote.last) + fees}
                        self.db.execute("INSERT INTO fills VALUES(?,?,?)", (fill["fill_id"], self.phase, json.dumps(fill)))
                        item["fill"] = fill
                    if quantity == order.quantity:
                        item["status"] = "FILLED"
                        item["events"].append("FILLED")
                    else:
                        if quantity:
                            item["events"].append("PARTIALLY_FILLED")
                        item["events"].append("CANCELLED")
                        item["status"] = "CANCELLED"
                        item["reason"] = "IOC remainder: liquidity/cash limit; no automatic retry"
                    result["orders"].append(item)
                result["status"] = "COMPLETED"
            self.db.execute("UPDATE accounts SET state=? WHERE phase=?", (json.dumps(state), self.phase))
            self.db.execute("INSERT INTO batches VALUES(?,?,?,?)", (batch_id, self.phase, intent, json.dumps(result)))
            return result
