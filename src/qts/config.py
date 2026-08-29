from __future__ import annotations

from pathlib import Path

import yaml


def load_config(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    required = {"environment", "instrument", "execution", "risk", "ibkr"}
    missing = required.difference(config)
    if missing:
        raise ValueError(f"Missing config sections: {', '.join(sorted(missing))}")
    return config

