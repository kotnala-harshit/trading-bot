from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REQUIRED = ("timestamp", "open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class DataReport:
    rows: int
    start: str
    end: str
    duplicates: int
    missing_values: int
    invalid_ohlc: int
    monotonic: bool

    @property
    def valid(self) -> bool:
        return self.rows > 1 and not any((self.duplicates, self.missing_values, self.invalid_ohlc)) and self.monotonic


def load_ohlcv(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    absent = set(REQUIRED).difference(frame.columns)
    if absent:
        raise ValueError(f"Missing columns: {', '.join(sorted(absent))}")
    frame = frame.loc[:, REQUIRED].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    for col in REQUIRED[1:]:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    return frame


def validate_ohlcv(frame: pd.DataFrame) -> DataReport:
    invalid = ((frame.high < frame[["open", "close", "low"]].max(axis=1)) | (frame.low > frame[["open", "close", "high"]].min(axis=1)) | (frame.volume < 0)).sum()
    return DataReport(
        rows=len(frame), start=str(frame.timestamp.min()), end=str(frame.timestamp.max()),
        duplicates=int(frame.timestamp.duplicated().sum()), missing_values=int(frame.isna().sum().sum()),
        invalid_ohlc=int(invalid), monotonic=bool(frame.timestamp.is_monotonic_increasing),
    )

