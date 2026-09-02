from __future__ import annotations

import os
from dataclasses import dataclass

import requests

from qts.broker import BrokerOrder, OrderRequest, OrderStatus, Quote


@dataclass
class UpstoxClient:
    """Small REST adapter for read-only quotes and sandbox order testing.

    Keep live order transmission outside this adapter until the production safety gate
    and broker-account reconciliation are enabled.
    """

    access_token: str
    sandbox_token: str | None = None
    timeout: int = 15

    @classmethod
    def from_env(cls) -> "UpstoxClient":
        token = os.getenv("UPSTOX_ACCESS_TOKEN", "")
        if not token:
            raise ValueError("UPSTOX_ACCESS_TOKEN is required for Upstox market data")
        return cls(token, os.getenv("UPSTOX_SANDBOX_TOKEN") or None)

    def _headers(self, sandbox: bool = False) -> dict[str, str]:
        token = self.sandbox_token if sandbox else self.access_token
        if not token:
            raise ValueError("UPSTOX_SANDBOX_TOKEN is required for sandbox orders")
        return {"Accept": "application/json", "Authorization": f"Bearer {token}"}

    def get_quote(self, instrument_key: str) -> Quote:
        response = requests.get(
            "https://api.upstox.com/v3/market-quote/ltp",
            params={"instrument_key": instrument_key},
            headers=self._headers(), timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json().get("data", {})
        if not payload:
            raise ValueError(f"No Upstox quote for {instrument_key}")
        item = next(iter(payload.values()))
        price = item.get("last_price") or item.get("ltp")
        if price is None:
            raise ValueError(f"Upstox quote missing last price for {instrument_key}")
        return Quote(symbol=instrument_key, last=float(price))

    def submit_sandbox_order(self, order: OrderRequest, instrument_token: str) -> BrokerOrder:
        response = requests.post(
            "https://sandbox.upstox.com/v3/order/place",
            json={
                "quantity": order.quantity,
                "product": "D",
                "validity": "DAY",
                "price": order.limit_price or 0,
                "instrument_token": instrument_token,
                "order_type": order.order_type,
                "transaction_type": order.side,
                "disclosed_quantity": 0,
                "trigger_price": 0,
                "is_amo": False,
                "slice": False,
                "tag": order.tag or "qts-paper",
            },
            headers={**self._headers(sandbox=True), "Content-Type": "application/json"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json().get("data", {})
        order_id = data.get("order_id")
        if not order_id:
            raise ValueError(f"Upstox sandbox did not return order_id: {response.text[:300]}")
        return BrokerOrder(order_id, order.symbol, order.side, order.quantity, 0, OrderStatus.SUBMITTED)
