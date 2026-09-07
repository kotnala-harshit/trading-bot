"""Three-phase paper runtime. Input bundles must contain timestamped observations."""
from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path

from qts.broker import Quote
from qts.paper_broker import PaperBroker

PHASES = ("india", "us", "global")


def load_phases(root: Path) -> dict:
    config = json.loads((root / "configs/phases.json").read_text())
    if config.get("transmit_orders") is not False:
        raise ValueError("transmit_orders must be false")
    if set(config) != {*PHASES, "transmit_orders", "execution", "promotion"}:
        raise ValueError("Exactly three phases are required")
    if config["execution"]["provider"] != "internal-paper":
        raise ValueError("Only internal paper execution supported")
    for phase in PHASES:
        item = config[phase]
        if item["environment"] not in {"research", "paper"}:
            raise ValueError("Live environment is not enabled")
        if item["max_positions"] != 5 or item["max_weight"] != 0.20:
            raise ValueError("Baseline remains five positions pending robust research")
    return config


def promotion_status(evidence: dict, policy: dict) -> dict:
    checks = {
        "paper_sessions": evidence.get("paper_sessions", 0) >= policy["minimum_paper_sessions"],
        "reviews": evidence.get("reviews", 0) >= policy["minimum_reviews"],
        "closed_trades": evidence.get("closed_trades", 0) >= policy["minimum_closed_trades"],
        "positive_net_return": evidence.get("net_return", -1) > 0,
        "benchmark_relative": evidence.get("excess_return", -1) >= 0,
        "drawdown": evidence.get("max_drawdown", -1) >= policy["max_drawdown"],
        "execution_shortfall": evidence.get("shortfall_bps", math.inf) <= policy["max_shortfall_bps"],
    }
    for key in ("holdout_passed", "walk_forward_passed", "nearby_parameters_passed", "cost_stress_passed",
                "reconciliation_clean", "no_stale_trades", "no_duplicate_orders", "stable_operation"):
        checks[key] = evidence.get(key) is True
    ready = all(checks.values())
    sandbox = evidence.get("sandbox_validated") is True
    status = "ELIGIBLE FOR SMALL LIVE PILOT" if ready and sandbox else (
        "SANDBOX VALIDATED" if sandbox else "PAPER VALIDATION" if evidence.get("paper_sessions", 0) else "NOT READY")
    return {"status": status, "checks": checks, "transmit_orders": False}


def atomic_json(path: Path, value: dict) -> None:
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = handle.name
    os.replace(temporary, path)


def observe_legacy(root: Path, phase: str, path: Path, state: dict, render) -> dict:
    # Legacy ledgers are evidence, not safe opening balances for the new broker.
    state = dict(state)
    state["last_attempt"] = datetime.now(UTC).isoformat()
    state["status"] = "Observation only: legacy execution retired; validated paper input bundle required"
    state["execution_blocked"] = True
    atomic_json(path, state)
    india = state if phase == "india" else json.loads((root / "runtime/paper_state.json").read_text())
    render(india, {})
    return state


def execute_bundle(root: Path, phase: str, bundle: dict) -> dict:
    config = load_phases(root)
    item, execution = config[phase], config["execution"]
    if item["environment"] != "paper":
        raise PermissionError(f"{phase} remains research; independent paper activation required")
    now = datetime.now(UTC)
    if bundle.get("market_open") is not True or bundle.get("corporate_actions_verified") is not True:
        raise ValueError("Official market session and corporate-action verification required")
    signal_at = datetime.fromisoformat(bundle["signal_at"])
    if signal_at.tzinfo is None or not signal_at < now:
        raise ValueError("Signal must precede execution")
    primary = {s: Quote(**q) for s, q in bundle["quotes"].items()}
    secondary = {s: Quote(**q) for s, q in bundle["validators"].items()}
    if any(q.provider != item["primary"] for q in primary.values()) or any(
        q.provider != item["validator"] for q in secondary.values()
    ):
        raise ValueError("Unexpected provider for phase")
    broker = PaperBroker(root / "runtime/ledgers" / f"{phase}.sqlite", phase, item["capital"])
    try:
        result = broker.rebalance(bundle["signal_id"], bundle["targets"], primary, secondary,
                                  now=now, max_positions=item["max_positions"], max_weight=item["max_weight"],
                                  fee_bps=execution["fee_bps"], slippage_bps=execution["slippage_bps"],
                                  max_age=execution["max_quote_age_seconds"],
                                  max_divergence_bps=execution["max_divergence_bps"])
        snapshot = {"environment": "PAPER", "data_mode": "realtime", "provider": item["primary"],
                    "state": broker.state(), "last_result": result, "reconciliation": broker.reconciliation(),
                    "quotes": bundle["quotes"], "last_run": now.isoformat(),
                    "fills": [json.loads(row[0]) for row in broker.db.execute("SELECT payload FROM fills WHERE phase=? ORDER BY rowid", (phase,))]}
        atomic_json(root / "runtime" / f"{phase}_platform.json", snapshot)
        return result
    finally:
        broker.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=PHASES, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    print(json.dumps(execute_bundle(root, args.phase, json.loads(args.bundle.read_text())), indent=2))


if __name__ == "__main__":
    main()
