from __future__ import annotations

import os
from dataclasses import dataclass

LIVE_ACK = "I_UNDERSTAND_REAL_MONEY_CAN_BE_LOST"


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reasons: tuple[str, ...]


def evaluate_live_gate(config: dict, env: dict[str, str] | None = None) -> SafetyDecision:
    values = os.environ if env is None else env
    reasons: list[str] = []
    execution = config.get("execution", {})
    if config.get("environment") != "live":
        reasons.append("configuration environment is not live")
    if execution.get("dry_run", True):
        reasons.append("dry_run is enabled")
    if not execution.get("autonomous_order_transmission", False):
        reasons.append("autonomous order transmission is disabled")
    required = {
        "TRADING_MODE": "live",
        "LIVE_TRADING_ENABLED": "true",
        "LIVE_TRADING_ACK": LIVE_ACK,
        "IBKR_ACCOUNT_CONFIRMED": "true",
    }
    for key, expected in required.items():
        if values.get(key, "").lower() != expected.lower():
            reasons.append(f"{key} acknowledgement missing")
    return SafetyDecision(not reasons, tuple(reasons))


def assert_order_allowed(config: dict, env: dict[str, str] | None = None) -> None:
    if config.get("environment") == "paper":
        return
    decision = evaluate_live_gate(config, env)
    if not decision.allowed:
        raise PermissionError("Live trading blocked: " + "; ".join(decision.reasons))

