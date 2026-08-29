from __future__ import annotations

import socket
from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerStatus:
    reachable: bool
    host: str
    port: int
    message: str


def check_ibkr(host: str, port: int, timeout: float = 1.0) -> BrokerStatus:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return BrokerStatus(
                True, host, port, "TCP endpoint reachable; authenticated API session not verified"
            )
    except OSError as exc:
        return BrokerStatus(False, host, port, f"Endpoint unavailable: {exc}")
