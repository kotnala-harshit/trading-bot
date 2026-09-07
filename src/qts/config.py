from __future__ import annotations

from pathlib import Path

import yaml


def load_config(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    required = {"environment", "execution", "risk"}
    required |= {"market_data"} if "market_data" in config else {"instrument", "ibkr"}
    missing = required.difference(config)
    if missing:
        raise ValueError(f"Missing config sections: {', '.join(sorted(missing))}")
    execution = config["execution"]
    if execution.get("transmit_orders", False) is not False:
        raise ValueError("Real-order transmission is disabled")
    if "market_data" in config:
        if config["environment"] != "paper" or execution.get("provider") != "internal-paper":
            raise ValueError("Realtime config must use internal paper execution")
        if config["risk"].get("max_positions") != 5 or config["risk"].get("max_position_weight") != 0.20:
            raise ValueError("Realtime India config must match five-position baseline")
    return config
