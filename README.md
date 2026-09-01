# Quant Trading Workbench

A single, deployable MES research and operational-readiness project. It includes an upload-driven Streamlit dashboard, deterministic moving-average research baseline, OHLCV validation, cost stress, IBKR endpoint diagnostics, Docker services, CI, and hard live-trading interlocks.

The primary product is Indian Equity Forecasting & Paper Trading with a ₹10,00,000 simulated mandate and a screenshot-derived watchlist. Phase 2 is US equities, Phase 3 is other global markets, Phase 4 is RoyaltyIQ, and Phase 5 is MES futures and derivatives. The system is paper-only and cannot guarantee zero losses.

> The bundled CSV is synthetic. It validates the software path, not a trading edge. The dashboard never places orders. Live autonomous transmission is disabled in the committed configuration.

The latest point-in-time factor search failed its blind five-year holdout and was not deployed. See [RESEARCH_RESULTS.md](RESEARCH_RESULTS.md) for the complete decision record.

## Automated paper trading on GitHub

GitHub Actions requests a paper-portfolio check every five minutes during NSE hours, the maximum GitHub cron frequency, using offset minutes to reduce scheduler congestion. GitHub may still delay or drop scheduled jobs. Monitoring runs use five-minute Yahoo convenience candles to refresh held-position prices without forcing a trade; 60-session reviews use five years of daily data to rank the current Nifty 50 by 63-session risk-adjusted momentum, hold five stocks, and retain existing holdings while they remain in the top ten. A 20% annualized Nifty volatility target scales equity exposure between 50% and 100%; unavailable risk data blocks paper orders. A robust price/volume/range anomaly veto remains active for new selections, stale quotes cannot trigger orders, and corporate actions are checked once per session. Results are simulated and saved in `runtime/`; the public summary shows the last successful scan, latest data timestamp, and a browser-side missed-scan warning.

Yahoo-adjusted OHLC data is used for total-return research. The forward paper ledger separately credits cash dividends, adjusts quantities and cost basis for reported splits/bonus-style ratios, deduplicates events, and reinvests available cash toward equal portfolio weights at the next 60-session review. Corporate-action data remains a convenience feed and should be reconciled against official company/exchange notices before any future live use.

This is suitable for forward-testing daily/swing decisions. GitHub schedules may be delayed and the public feed is not exchange-grade, so it is not suitable for exact intraday execution. No broker credentials are used and real orders remain disabled.

The emergency portfolio circuit breaker liquidates paper positions at a 20% drawdown, pauses entries for 28 calendar days, resets the paper high-water mark, and requires all market and stock gates to pass again before re-entry. Historical testing showed that the previous 5% threshold repeatedly sold normal equity volatility and materially harmed results. The wider threshold preserves a final-loss backstop without pretending that ordinary drawdowns can be eliminated. It is not a guarantee against gaps or larger losses.

The automation is enabled by [`configs/paper-trader.json`](configs/paper-trader.json). To stop new paper activity from GitHub, change `"enabled": true` to `false` and commit it on `main`. Existing positions remain recorded but no simulated orders are created while disabled.

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
