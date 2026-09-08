# Three-phase systematic research and paper trading

Exactly three active phases: **India**, **US**, **Global**. Real-money transmission remains disabled. This checkout prepares live-data paper execution; it is not yet an authenticated, unattended broker-data deployment.

## Current operational boundary

The old Yahoo/GitHub paper execution loops were retired because they bypassed reconciliation, accepted same-day stale data, and wrote state and fills separately. Their scheduled weekday observation runs now refresh status and the dashboard during India/US hours; they do not create orders. Existing legacy ledgers remain unchanged as evidence; no unverified balances are imported into the new broker.

The new `qts.platform` entry point accepts a timestamped, independently validated input bundle and executes only internal paper orders. India is configured for paper; US/global remain research until independently enabled for paper validation. None can transmit real orders, even if a caller asks for it.

Market data → completed-session ranking → one target per security → quote and risk validation → ledger reconciliation → sell-before-buy order plan → internal paper fills → atomic SQLite state → shared Pages/Streamlit phase model.

## Strategy and universes

- **India:** preserve the 63-session risk-adjusted momentum / 5-position / top-10 retention / 60-session review reference. Next-open research, 20% emergency drawdown threshold and 28 calendar-day cooldown. The realtime config now agrees on five positions and 20% maximum target weight. Broader research begins with audited PIT Nifty 100, then Nifty 200 if data quality supports it. Require 252 observations, ₹50 raw price and ₹10 crore median daily traded value over 60 sessions, dated membership/security identity, current observations and corporate-action quality. Thresholds are predeclared research filters, not empirically validated optimal values. Nifty 500 requires a separate coverage audit.
- **US:** current liquid ETF diagnostic basket SPY, IWM, MDY, RSP, QQQ against adjusted SPY; PIT stock selection remains a challenger pending reliable delisted-stock coverage. Highly correlated ETFs are not claimed to diversify country exposure.
- **Global:** one country/region ETF for United States (SPY), Canada (EWC), United Kingdom (EWU), Eurozone (EZU), Switzerland (EWL), Japan (EWJ), Australia (EWA), Hong Kong (EWH), Singapore (EWS), India (INDA), Taiwan (EWT), South Korea (EWY), Brazil (EWZ). Benchmark VT; USD-listed proxies, with local economic/FX exposure. One instrument per country and a 20% target cap limit US dominance. Correlation/sector overlap still needs separate validation. Liquidity filters may exclude a market; do not silently relax them.

No new strategy is promoted. The prior 108-configuration factor search failed out of sample and remains rejected. Old rotation research is preserved only in `archive/rejected_rotation/`, with no active UI, config, scheduler or strategy import.

## Run locally

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
ruff check .
pytest -q
python -m compileall -q src scripts app.py
python -m qts.dashboard
streamlit run app.py
```

The two dashboards share `qts.dashboard.phase_snapshot`. Missing operational metrics show “Not measured”; missing reconciliation shows failure/unverified, never a fabricated PASS. Archived forward observations are explicitly delayed Yahoo data. The realtime config expresses a target integration, not proof of a live feed.

## Validated paper input

```
python -m qts.platform --phase india --bundle /private/path/validated-input.json
```

Bundle fields: `signal_id`, `signal_at` (aware UTC datetime), `targets` (stable security ID → integer shares), `quotes`, `validators`, `market_open: true`, `corporate_actions_verified: true`. Each quote contains `symbol,last,bid,ask,timestamp,provider,bid_size,ask_size`. Providers must match phase settings and security identities must agree. The trusted collector must establish official session and corporate-action facts; these input attestations are not a replacement for the remaining provider integration.

The engine persists deterministic rebalance/order/fill IDs, rejects changed targets under an existing signal ID, crosses ask/bid plus adverse slippage, estimates fees, caps fills at displayed size, cancels IOC remainders, and blocks new orders on ledger mismatch. Replays return the stored result. A failed database write rolls back balances and fills. Default execution budget is 10 bps fees + 5 bps adverse slippage, with spread additionally measured from quotes.

Promotion gates require sufficient sessions/reviews/closed trades, positive net and benchmark-relative returns, drawdown and shortfall limits, holdout/walk-forward/neighbor/cost robustness and clean operational evidence. Sandbox validation alone cannot qualify a phase for a pilot. No real broker-order dispatch is implemented in this platform.

See [data contracts and research commands](DATA_ARCHITECTURE.md), [official provider matrix](PROVIDERS.md), [rebuild evidence and remaining work](REBUILD_REPORT.md), and [historical research record](RESEARCH_RESULTS.md).

## Deployment

Review the local diff before committing or pushing. After approval, CI checks the code and generates Pages; the existing Pages workflow publishes `docs/`. Durable SQLite execution belongs on a single persistent host with backups, not an ephemeral GitHub runner. Authenticate primary and validator feeds, map the security master, integrate official sessions/actions, and prove recovery before enabling unattended paper execution. Keep secrets out of Git and public dashboard artifacts.
