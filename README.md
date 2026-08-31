# Quant Trading Workbench

A single, deployable MES research and operational-readiness project. It includes an upload-driven Streamlit dashboard, deterministic moving-average research baseline, OHLCV validation, cost stress, IBKR endpoint diagnostics, Docker services, CI, and hard live-trading interlocks.

The primary product is Indian Equity Forecasting & Paper Trading with a ₹10,00,000 simulated mandate and a screenshot-derived watchlist. Phase 2 is US equities, Phase 3 is other global markets, Phase 4 is RoyaltyIQ, and Phase 5 is MES futures and derivatives. The system is paper-only and cannot guarantee zero losses.

> The bundled CSV is synthetic. It validates the software path, not a trading edge. The dashboard never places orders. Live autonomous transmission is disabled in the committed configuration.

## Automated paper trading on GitHub

GitHub Actions scans a liquid Indian-equity watchlist every 30 minutes during NSE hours. It uses delayed Yahoo daily data, a long/cash 20/80-day trend signal, a historical drawdown/Sharpe gate, a 5% planning stop, a maximum of six positions, 15% allocation and 0.5% planned risk per position. Results are simulated and saved in `runtime/`; the public summary is deployed through GitHub Pages.

This is suitable for forward-testing daily/swing decisions. GitHub schedules may be delayed and the public feed is not exchange-grade, so it is not suitable for exact intraday execution. No broker credentials are used and real orders remain disabled.

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
