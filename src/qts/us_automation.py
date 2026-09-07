from __future__ import annotations

import argparse
import csv
import io
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

from qts.providers import yahoo_chart

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "runtime" / "us_paper_state.json"
LEDGER_PATH = ROOT / "runtime" / "us_paper_ledger.csv"
CONTROL_PATH = ROOT / "configs" / "paper-trader.json"
MEMBERSHIP_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/"
    "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"
)
CAPITAL, MAX_POSITIONS, KEEP_RANK, REVIEW_SESSIONS = 10_000.0, 5, 15, 120
FEE_BPS, TARGET_VOL, MAX_EXPOSURE = 5.0, 0.07, 0.40


def us_market_is_open(now: datetime | None = None) -> bool:
    local = (now or datetime.now(UTC)).astimezone(ZoneInfo("America/New_York"))
    minutes = local.hour * 60 + local.minute
    return local.weekday() < 5 and 9 * 60 + 30 <= minutes <= 16 * 60


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {
        "cash": CAPITAL,
        "positions": {},
        "peak_equity": CAPITAL,
        "last_equity": CAPITAL,
        "sessions_since_review": REVIEW_SESSIONS,
        "status": "Waiting for first US market-hours paper run",
    }


def save(state: dict, fills=()) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))
    if not fills:
        return
    exists = LEDGER_PATH.exists()
    with LEDGER_PATH.open("a", newline="") as handle:
        writer = csv.writer(handle)
        if not exists:
            writer.writerow(["timestamp", "symbol", "side", "quantity", "price", "fees"])
        for fill in fills:
            writer.writerow(
                [fill.timestamp, fill.symbol, fill.side, fill.quantity, fill.price, fill.fees]
            )


def current_members() -> list[str]:
    response = requests.get(MEMBERSHIP_URL, timeout=30)
    response.raise_for_status()
    history = pd.read_csv(io.StringIO(response.text))
    return sorted(symbol.replace(".", "-") for symbol in history.iloc[-1].tickers.split(","))


def fetch(symbol: str, review: bool):
    try:
        return yahoo_chart(symbol, "5y" if review else "1d", "1d" if review else "5m")
    except (OSError, ValueError, TypeError, KeyError, requests.RequestException):
        return None


def exposure(spy: pd.DataFrame) -> float:
    if len(spy) < 201 or spy.close.iloc[-1] <= spy.close.ewm(span=200).mean().iloc[-1]:
        return 0.0
    volatility = float(spy.close.pct_change().tail(20).std() * math.sqrt(252))
    return min(MAX_EXPOSURE, TARGET_VOL / volatility) if np.isfinite(volatility) and volatility > 0 else 0.0


def run(force: bool = False) -> dict:
    from qts.automation import render_page
    from qts.platform import observe_legacy
    return observe_legacy(ROOT, "us", STATE_PATH, load_state(), render_page)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    print(json.dumps(run(parser.parse_args().force), indent=2))


if __name__ == "__main__":
    main()
