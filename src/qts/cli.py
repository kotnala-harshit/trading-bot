from __future__ import annotations

import argparse
import json

from qts.config import load_config
from qts.readiness import check_ibkr
from qts.safety import evaluate_live_gate


def doctor(config_path: str, require_ibkr: bool = False) -> int:
    config = load_config(config_path)
    status = check_ibkr(config["ibkr"]["host"], int(config["ibkr"]["port"]))
    gate = evaluate_live_gate(config)
    report = {
        "environment": config["environment"],
        "ibkr": status.__dict__,
        "live_gate": {"allowed": gate.allowed, "reasons": gate.reasons},
    }
    print(json.dumps(report, indent=2))
    return 1 if require_ibkr and not status.reachable else 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="qts")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("doctor")
    check.add_argument("--config", default="configs/production-paper.yaml")
    check.add_argument("--require-ibkr", action="store_true")
    args = parser.parse_args()
    raise SystemExit(doctor(args.config, args.require_ibkr))
