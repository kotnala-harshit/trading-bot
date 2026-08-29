from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests


@dataclass(frozen=True)
class MarketDataset:
    frame: pd.DataFrame
    provider: str
    symbol: str
    research_grade: bool
    note: str


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    columns = {str(column).lower().replace(" ", "_"): column for column in frame.columns}
    required = ("timestamp", "open", "high", "low", "close", "volume")
    missing = set(required).difference(columns)
    if missing:
        raise ValueError(f"Provider response is missing: {', '.join(sorted(missing))}")
    result = frame[[columns[name] for name in required]].copy()
    result.columns = list(required)
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    return result.sort_values("timestamp").dropna().reset_index(drop=True)


def yahoo_chart(
    symbol: str = "MES=F", period: str = "1y", interval: str = "1d"
) -> MarketDataset:
    response = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        params={"range": period, "interval": interval, "events": "history"},
        headers={"User-Agent": "Mozilla/5.0 QuantTradingWorkbench/5.1"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()["chart"]
    if payload.get("error") or not payload.get("result"):
        raise ValueError(f"Yahoo returned no data: {payload.get('error')}")
    result = payload["result"][0]
    quote = result["indicators"]["quote"][0]
    frame = pd.DataFrame({"timestamp": result["timestamp"], **quote})
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="s", utc=True)
    return MarketDataset(
        frame=_normalize(frame),
        provider="Yahoo Finance",
        symbol=symbol,
        research_grade=False,
        note="Continuous convenience symbol; not contract-level and not suitable for final MES validation.",
    )


def alpha_vantage_daily(symbol: str, api_key: str) -> MarketDataset:
    if not api_key:
        raise ValueError("Add ALPHA_VANTAGE_API_KEY to Streamlit secrets first.")
    response = requests.get(
        "https://www.alphavantage.co/query",
        params={"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": "compact", "apikey": api_key},
        timeout=30,
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    series = payload.get("Time Series (Daily)")
    if not series:
        message = payload.get("Note") or payload.get("Information") or payload.get("Error Message")
        raise ValueError(message or "Alpha Vantage returned no daily series.")
    rows = [
        {
            "timestamp": day,
            "open": values["1. open"],
            "high": values["2. high"],
            "low": values["3. low"],
            "close": values["4. close"],
            "volume": values["5. volume"],
        }
        for day, values in series.items()
    ]
    return MarketDataset(
        frame=_normalize(pd.DataFrame(rows)),
        provider="Alpha Vantage",
        symbol=symbol,
        research_grade=False,
        note="Stock daily feed; useful for the future stock module, not contract-level MES futures research.",
    )
