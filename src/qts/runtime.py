from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from qts.config import load_config
from qts.safety import evaluate_live_gate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/production-paper.yaml")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    if config["environment"] == "live" and not evaluate_live_gate(config).allowed:
        raise SystemExit("Live runtime blocked by safety gate")
    target = Path("runtime/heartbeat.json")
    target.parent.mkdir(exist_ok=True)
    while True:
        target.write_text(
            json.dumps(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "environment": config["environment"],
                    "status": "healthy",
                },
                indent=2,
            )
        )
        if args.once:
            return
        time.sleep(30)
