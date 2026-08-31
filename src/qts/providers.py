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


@dataclass(frozen=True)
class CorporateAction:
    event_id: str
    symbol: str
    kind: str
    timestamp: str
    amount: float = 0.0
    numerator: float = 1.0
    denominator: float = 1.0


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


def yahoo_chart(symbol: str = "MES=F", period: str = "1y", interval: str = "1d") -> MarketDataset:
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
    adjusted = result["indicators"].get("adjclose", [{}])[0].get("adjclose")
    if adjusted:
        raw_close = pd.Series(quote["close"], dtype=float)
        ratio = pd.Series(adjusted, dtype=float) / raw_close
        for column in ("open", "high", "low", "close"):
            quote[column] = (pd.Series(quote[column], dtype=float) * ratio).tolist()
    frame = pd.DataFrame({"timestamp": result["timestamp"], **quote})
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="s", utc=True)
    return MarketDataset(
        frame=_normalize(frame),
        provider="Yahoo Finance",
        symbol=symbol,
        research_grade=False,
        note="Continuous convenience symbol; not contract-level and not suitable for final MES validation.",
    )


def _parse_corporate_actions(result: dict[str, Any], symbol: str) -> list[CorporateAction]:
    actions = []
    events = result.get("events", {})
    for event_id, event in events.get("dividends", {}).items():
        actions.append(
            CorporateAction(
                event_id=f"{symbol}:dividend:{event_id}", symbol=symbol, kind="DIVIDEND",
                timestamp=pd.to_datetime(event["date"], unit="s", utc=True).isoformat(),
                amount=float(event["amount"]),
            )
        )
    for event_id, event in events.get("splits", {}).items():
        actions.append(
            CorporateAction(
                event_id=f"{symbol}:split:{event_id}", symbol=symbol, kind="SPLIT",
                timestamp=pd.to_datetime(event["date"], unit="s", utc=True).isoformat(),
                numerator=float(event["numerator"]), denominator=float(event["denominator"]),
            )
        )
    return sorted(actions, key=lambda action: action.timestamp)


def yahoo_corporate_actions(symbol: str, period: str = "3mo") -> list[CorporateAction]:
    response = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        params={"range": period, "interval": "1d", "events": "div,splits"},
        headers={"User-Agent": "Mozilla/5.0 QuantTradingWorkbench/5.1"}, timeout=20,
    )
    response.raise_for_status()
    payload = response.json()["chart"]
    if payload.get("error") or not payload.get("result"):
        raise ValueError(f"Yahoo returned no data: {payload.get('error')}")
    return _parse_corporate_actions(payload["result"][0], symbol)


def alpha_vantage_daily(symbol: str, api_key: str) -> MarketDataset:
    if not api_key:
        raise ValueError("Add ALPHA_VANTAGE_API_KEY to Streamlit secrets first.")
    response = requests.get(
        "https://www.alphavantage.co/query",
        params={
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "compact",
            "apikey": api_key,
        },
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
