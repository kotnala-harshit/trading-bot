# Quant Trading Workbench

A single, deployable MES research and operational-readiness project. It includes an upload-driven Streamlit dashboard, deterministic moving-average research baseline, OHLCV validation, cost stress, IBKR endpoint diagnostics, Docker services, CI, and hard live-trading interlocks.

The primary product is Indian Equity Forecasting & Paper Trading with a ₹10,00,000 simulated mandate and a screenshot-derived watchlist. Phase 2 is US equities, Phase 3 is other global markets, Phase 4 is RoyaltyIQ, and Phase 5 is MES futures and derivatives. The system is paper-only and cannot guarantee zero losses.

> The bundled CSV is synthetic. It validates the software path, not a trading edge. The dashboard never places orders. Live autonomous transmission is disabled in the committed configuration.

## Automated paper trading on GitHub

GitHub Actions scans a liquid Indian-equity watchlist every 30 minutes during NSE hours. It uses delayed Yahoo daily data, a Nifty 200-day regime filter, a 20/80-day stock trend signal, positive six-month momentum, a 45% volatility ceiling, and a robust price/volume/range anomaly veto inspired by the companion market-surveillance project. The portfolio retains a 5% planning stop, maximum six positions, 15% allocation and 0.5% planned risk per position. Results are simulated and saved in `runtime/`; the public summary is deployed through GitHub Pages.

This is suitable for forward-testing daily/swing decisions. GitHub schedules may be delayed and the public feed is not exchange-grade, so it is not suitable for exact intraday execution. No broker credentials are used and real orders remain disabled.

The portfolio circuit breaker liquidates paper positions at a 5% drawdown, pauses entries for 28 calendar days, resets the paper high-water mark, and requires all market and stock gates to pass again before re-entry. It is not a guarantee against gaps or larger losses.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,ibkr]'
pytest -q
streamlit run app.py
```

Open <http://localhost:8501>. For the full private GitHub, Streamlit Community Cloud, Docker, and IBKR setup, see [START_HERE.md](START_HERE.md).

## Safety boundary

This repository is production-shaped for paper/staging operations. It is not certified as profitable, fault-tolerant, or suitable for unattended real-money trading. Live promotion requires a deliberate config change plus four runtime acknowledgements; it also requires completing the evidence checklist in [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md).
