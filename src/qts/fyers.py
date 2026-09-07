"""Read-only independent India depth snapshot; no order methods."""
from __future__ import annotations

import os
from datetime import UTC, datetime

import requests

from qts.broker import Quote


def parse_depth(payload: dict, provider_symbol: str, security_id: str) -> Quote:
    if payload.get("s") != "ok":
        raise ValueError("FYERS depth request unsuccessful")
    item = payload.get("d", {}).get(provider_symbol)
    if not item or not item.get("ltt") or not item.get("bids") or not item.get("ask"):
        raise ValueError("Missing FYERS identity/depth/trade timestamp")
    bid = max(item["bids"], key=lambda x: x["price"])
    asks = [x for x in item["ask"] if x["price"] > 0]
    if not asks:
        raise ValueError("No executable FYERS ask")
    ask = min(asks, key=lambda x: x["price"])
    # Conservative ltt freshness: no invented receipt-time quote stamp.
    timestamp = datetime.fromtimestamp(float(item["ltt"]), UTC).isoformat()
    return Quote(security_id, float(item["ltp"]), float(bid["price"]), float(ask["price"]),
                 timestamp, "fyers", int(bid["volume"]), int(ask["volume"]))


def get_depth(provider_symbol: str, security_id: str) -> Quote:
    app, token = os.environ.get("FYERS_APP_ID"), os.environ.get("FYERS_ACCESS_TOKEN")
    if not app or not token:
        raise ValueError("FYERS_APP_ID and FYERS_ACCESS_TOKEN required")
    response = requests.get("https://api-t1.fyers.in/data/depth",
                            params={"symbol": provider_symbol, "ohlcv_flag": 1},
                            headers={"Authorization": f"{app}:{token}"}, timeout=15)
    response.raise_for_status()
    return parse_depth(response.json(), provider_symbol, security_id)
