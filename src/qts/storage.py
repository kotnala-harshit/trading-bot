"""Immutable raw objects and time-bounded security identities."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


def store_raw(root: Path, payload: bytes) -> Path:
    digest = hashlib.sha256(payload).hexdigest()
    path = root / (digest + ".json")
    root.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise ValueError("Raw object hash collision/corruption") from None
    return path


def resolve_security(master: pd.DataFrame, provider: str, symbol: str, day) -> str:
    day = pd.Timestamp(day)
    rows = master[(master.provider == provider) & (master.symbol == symbol)
                  & (master.valid_from <= day) & (master.valid_to > day)
                  & (master.known_at <= day)]
    if len(rows) != 1:
        raise ValueError("Missing/ambiguous security identity")
    return str(rows.iloc[0].security_id)


def normalize_yahoo(payload: bytes, security_id: str) -> pd.DataFrame:
    result = json.loads(payload)["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    frame = pd.DataFrame({"date": pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_localize(None).normalize(), **quote})
    adjusted = result["indicators"].get("adjclose", [{}])[0].get("adjclose")
    if adjusted is None:
        raise ValueError("Adjusted total-return series required")
    ratio = pd.Series(adjusted) / frame.close
    frame["raw_close"] = frame.close
    frame["traded_value"] = frame.close * frame.volume
    for field in ("open", "high", "low", "close"):
        frame[field] *= ratio
    frame["quality_ok"] = frame[["open", "close", "traded_value"]].notna().all(axis=1) & (ratio > 0)
    frame["security_id"] = security_id
    # No filling missing observations, no double-counting cash dividends on adjusted returns.
    return frame
