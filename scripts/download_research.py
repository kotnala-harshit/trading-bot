"""Download current ETF diagnostic basket; not a point-in-time stock universe."""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

from qts.storage import normalize_yahoo, store_raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["us", "global"], required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "configs/phases.json").read_text())[args.phase]
    symbols = config.get("etfs") or list(config["markets"].values())
    benchmark = "SPY" if args.phase == "us" else "VT"
    frames, provenance, errors = [], [], {}
    benchmark_frame = None
    for symbol in sorted(set(symbols + [benchmark])):
        try:
            response = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                                    params={"range": "10y", "interval": "1d", "events": "history"},
                                    headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            response.raise_for_status()
            raw = store_raw(root / "data/raw/yahoo", response.content)
            frame = normalize_yahoo(response.content, symbol)
            if not frame.quality_ok.all():
                raise ValueError("Missing/invalid observations; audit raw data")
            if symbol == benchmark:
                benchmark_frame = frame
            if symbol in symbols:
                frames.append(frame)
            provenance.append({"symbol": symbol, "raw_object": str(raw.relative_to(root)), "rows": len(frame)})
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            errors[symbol] = type(exc).__name__ + ": " + str(exc)
    output = root / "data/normalized" / args.phase
    output.mkdir(parents=True, exist_ok=True)
    (output / "provenance.json").write_text(json.dumps({"downloaded_at": datetime.now(UTC).isoformat(),
        "purpose": "CURRENT ETF BASKET DIAGNOSTIC; identity/inception and liquidity not independently verified; no promotion",
        "objects": provenance, "errors": errors}, indent=2))
    if errors or benchmark_frame is None:
        raise SystemExit("Incomplete download; see provenance.json; no partial research dataset exported")
    prices = pd.concat(frames)
    prices.to_csv(output / "prices.csv", index=False)
    benchmark_frame.to_csv(output / "benchmark.csv", index=False)
    # Fixed ex-post ETF basket is explicitly a diagnostic, not purported historical index membership.
    members = pd.DataFrame([{"security_id": s, "effective_from": f.date.min(),
                             "effective_to": pd.Timestamp("2100-01-01"), "known_at": f.date.min()}
                            for s, f in prices.groupby("security_id")])
    members.to_csv(output / "diagnostic_membership.csv", index=False)
    print(f"Downloaded {len(frames)} ETF histories; current-basket diagnostic only")


if __name__ == "__main__":
    main()
