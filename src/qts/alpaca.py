"""Read-only Alpaca IEX quote snapshots; no order methods."""
from __future__ import annotations

import os

import requests

from qts.broker import Quote


def parse_quote(payload: dict, security_id: str) -> Quote:
    item = payload.get("quote")
    if not item or not item.get("t") or item.get("bp") is None or item.get("ap") is None:
        raise ValueError("Missing Alpaca IEX bid, ask, or timestamp")
    last = (float(item["bp"]) + float(item["ap"])) / 2
    return Quote(security_id, last, float(item["bp"]), float(item["ap"]), item["t"], "alpaca-iex",
                 int(item.get("bs", 0)), int(item.get("as", 0)))


def get_quote(symbol: str, security_id: str | None = None) -> Quote:
    key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_API_SECRET")
    if not key or not secret:
        raise ValueError("ALPACA_API_KEY and ALPACA_API_SECRET required")
    response = requests.get(
        f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest", params={"feed": "iex"},
        headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}, timeout=15,
    )
    response.raise_for_status()
    return parse_quote(response.json(), security_id or symbol)
