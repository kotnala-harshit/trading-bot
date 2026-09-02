from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class OrderStatus(str, Enum):
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Quote:
    symbol: str
    last: float
    bid: float | None = None
    ask: float | None = None
    timestamp: str | None = None


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    quantity: int
    order_type: str = "MARKET"
    limit_price: float | None = None
    tag: str | None = None


@dataclass(frozen=True)
class BrokerOrder:
    order_id: str
    symbol: str
    side: str
    quantity: int
    filled_quantity: int
    status: OrderStatus
    average_price: float | None = None


class Broker(Protocol):
    """Execution boundary. Strategies must never call a concrete broker directly."""

    def get_quote(self, symbol: str) -> Quote: ...
    def get_positions(self) -> dict[str, int]: ...
    def get_cash(self) -> float: ...
    def get_open_orders(self) -> list[BrokerOrder]: ...
    def submit_order(self, order: OrderRequest) -> BrokerOrder: ...
    def cancel_order(self, order_id: str) -> BrokerOrder: ...
    def get_order(self, order_id: str) -> BrokerOrder: ...
