# Rebuild report — 7 September 2026

## 1. Architecture changes and completion boundary

Implemented and tested a local research + durable internal-paper foundation with a shared three-phase dashboard. **This is not yet the complete authenticated live-data platform.** No real order transmission is enabled. No new strategy has been promoted.

The requested old checkout `/Users/harshitkotnala/job-dashboard/trading-bot` did not exist. The current workspace was empty, so the requested GitHub repository was cloned into `/Users/harshitkotnala/Documents/ChatGPT/trading bot`. Starting revision: `fe88384bd4c6cb625d79d1ef8de11edabb7c13cb`. Starting Git state: clean.

Audit covered source, config, tests, workflow schedules, committed research artifacts, legacy account/ledger state and deployed HTML before edits. Deployed HTML was accessible and differed from the tracked dashboard snapshot (deployed SHA256 `f6a62cebb7d62dfb2672fe8b5add4ebc0a3be4cbdd18e52fc800ae673e39748b`). Both exposed the rejected rotation phase. No historical India raw/PIT data or authenticated provider session was present.

Execution now has deterministic signal/rebalance/order/fill identities, atomic SQLite balances and fills, ledger replay reconciliation, independent quote validation, conservative bid/ask fills, fees/slippage, displayed-size partial fills and IOC cancellation. Database-write failure rolls back the full transaction; repeat signal IDs return the original result and conflicting targets are rejected. The shared completed-session ranking and planner create one target per security. The new execution CLI currently accepts a trusted validated input bundle; an unattended collector/scheduler joining these components remains outstanding.

The old scheduler code could place fills without broker reconciliation and accepted any same-day quote. That execution path is removed and old cron triggers are removed locally. Manual legacy commands only preserve observation status and render the dashboard. Legacy paper controls are false. This is an operational behavior change to review before deployment.

## 2. Exact new files (including archived copies)

- `DATA_ARCHITECTURE.md`
- `PROVIDERS.md`
- `REBUILD_REPORT.md`
- `archive/rejected_rotation/README.md`
- `archive/rejected_rotation/phase25_research.py`
- `archive/rejected_rotation/phase25_results.json`
- `archive/rejected_rotation/test_phase25.py`
- `artifacts/rebuild_results.json`
- `configs/phases.json`
- `data/backtests/.gitkeep`
- `data/corporate_actions/.gitkeep`
- `data/features/.gitkeep`
- `data/live_cache/.gitkeep`
- `data/normalized/.gitkeep`
- `data/schemas.json`
- `data/security_master/.gitkeep`
- `data/universe_membership/.gitkeep`
- `scripts/download_research.py`
- `src/qts/dashboard.py`
- `src/qts/fyers.py`
- `src/qts/paper_broker.py`
- `src/qts/planning.py`
- `src/qts/platform.py`
- `src/qts/research.py`
- `src/qts/storage.py`
- `tests/test_platform.py`
- `tests/test_research_pipeline.py`

## 3. Exact modified files

- `.github/workflows/ci.yml`
- `.github/workflows/paper-trader.yml`
- `.github/workflows/us-paper-trader.yml`
- `.gitignore`
- `README.md`
- `app.py`
- `configs/paper-trader.json`
- `configs/production-live.yaml`
- `configs/production-paper.yaml`
- `configs/realtime-paper.yaml`
- `configs/staging.yaml`
- `docs/index.html`
- `src/qts/automation.py`
- `src/qts/broker.py`
- `src/qts/config.py`
- `src/qts/execution.py`
- `src/qts/paper.py`
- `src/qts/runtime.py`
- `src/qts/safety.py`
- `src/qts/upstox.py`
- `src/qts/us_automation.py`
- `tests/test_automation.py`
- `tests/test_safety.py`

## 4. Exact removed/archived files

- `artifacts/phase25_results.json` → `archive/rejected_rotation/phase25_results.json`
- `scripts/phase25_research.py` → `archive/rejected_rotation/phase25_research.py`
- `tests/test_phase25.py` → `archive/rejected_rotation/test_phase25.py`

The archive is explicitly REJECTED / ARCHIVED. Its historical test is retained for provenance, not collected as an active test. Original forward paper ledger and account files were not rewritten.

## 5. Rotation removal

No rotation section remains in generated Pages, Streamlit navigation, active strategy code, configs or workflows. The only active-test mention asserts it is absent. Historical discussion remains in `RESEARCH_RESULTS.md`, and archived files are not imported by runtime. Pages deployment itself awaits review and push.

## 6. India universe design

Start with audited point-in-time Nifty 100 large/mid-cap membership, expand to Nifty 200 only after coverage checks; do not ingest all NSE equities. Require stable dated security IDs, published membership intervals, 252 observations, raw price at least ₹50, 60-session median traded value at least ₹10 crore, latest-session presence and valid corporate-action history. Nifty 500 is not activated. These thresholds are design choices, not claims of optimality.

Retain the five-position reference. The nearby research set changes one dimension at a time: 5/7/8/10 positions, 42/63/84 lookback, 40/60/80 review; no factorial sweep. Reliable PIT India data, delisting treatment and Nifty TRI must be acquired before the broader baseline comparison can be executed.

## 7. US universe design

Current-basket diagnostic core: SPY, IWM, MDY, RSP, QQQ; adjusted SPY benchmark. Minimum 252 observations, $5 price and $20m median daily traded value. PIT individual-stock selection is not promoted: previously downloaded coverage gaps make an active-versus-passive claim unreliable. The five-ETF basket's 7/8/10-position variants primarily increase cash rather than genuine breadth and must not be interpreted as evidence for larger stock portfolios.

## 8. Global markets

United States/SPY, Canada/EWC, United Kingdom/EWU, Eurozone/EZU, Switzerland/EWL, Japan/EWJ, Australia/EWA, Hong Kong/EWH, Singapore/EWS, India/INDA, Taiwan/EWT, South Korea/EWY, Brazil/EWZ. USD-listed country proxies, adjusted VT benchmark, one selected instrument per country and 20% target cap. Minimum $10m median daily traded value; markets failing the filter stay excluded. Economic exposures remain correlated; holdings/sector/FX concentration auditing is still required. The research simulator allows price drift between reviews; the 20% cap is a target, not continuous rebalancing.

## 9. API and sandbox provider matrix

See `PROVIDERS.md` for live/history/order/sandbox/streaming/cost/account comparisons with official source links. Upstox + FYERS + internal paper + a separate Upstox Sandbox token remains the India direction. Upstox full-quote and FYERS depth parsers/read-only REST adapters are implemented and fixture-tested. No authenticated calls or sandbox orders were executed. Alpaca IEX and IBKR entitled data are planned US/global inputs, not active integrations. IEX is a single-exchange feed and is not consolidated NBBO.

## 10. Data storage

`DATA_ARCHITECTURE.md` and `data/schemas.json` define raw, normalized, security-master, membership, actions, live-cache, feature, backtest, ledger/order/reconciliation boundaries. Raw bytes are content-addressed with exclusive creation. Normalized adjusted prices are separate from raw executable prices. Historical datasets, SQLite state and provider caches are ignored by Git. A compact research summary is retained in `artifacts/rebuild_results.json`.

## 11. Strategy changes

No promotion. Five-position India config mismatch fixed to 5 and 0.20. Default paper budget: 10 bps fees plus 5 bps adverse slippage, with observed spread charged additionally. Research's 15 bps is combined one-way cost, not a claim that it exactly reproduces time-varying live spread. The previous Yahoo volatility-overlay forward path is retired and not relabelled as the historically preferred baseline. Emergency drawdown/cooldown blocks new entries; only liquidation targets may execute during cooldown. No automatic emergency signal collector is yet connected.

ETERNAL investigation: 613-share entry plus a one-share reinvestment/top-up occurred within the same review; the two loops caused the duplicate-looking rows. They were not identical duplicated fills. Historical rows remain unchanged; the new target planner removes the separate top-up order path.

## 12. Research actually executed

Downloaded adjusted Yahoo histories for all five US ETFs and all thirteen global ETFs plus VT. Raw payload hashes and provenance are stored locally. Both are explicitly current-selected ETF diagnostics, **not PIT stock-universe tests or a new genuinely blind holdout**.

Development ends 2021-08-31; validation ends 2023-08-31; the later slice begins 2023-09-01 and is labelled `holdout_already_opened_not_blind`. Warm-up requires 252 observations; full results cover approximately nine years of the downloaded ten-year data. Each phase executed four main windows, seven cost scenarios, eight predefined development-only neighboring configurations and six fixed-baseline walk-forward slices. Rolling 3M/6M/1Y/3Y/5Y windows are sampled quarterly. Short-window CAGR is omitted under one year. All calculations are offline and reproducible.

### US — executed full window 2017-09-06 to 2026-09-04

Starting $10,000 → $22,242.67; total return 122.43%; CAGR 9.30%; benchmark CAGR 15.27%; maximum drawdown -29.39%; 20 closed trades; win rate 60.0%. **Trailed benchmark; not promoted.**

Cost stress (one-way bps → CAGR): 0 → 9.46%, 5 → 9.41%, 10 → 9.35%, 15 → 9.30%, 20 → 9.24%, 30 → 9.13%, 50 → 8.91%.

Rolling window counts: 3m: 35, 6m: 34, 12m: 32, 36m: 24, 60m: 16.

### GLOBAL — executed full window 2017-09-06 to 2026-09-04

Starting $10,000 → $21,423.94; total return 114.24%; CAGR 8.84%; benchmark CAGR 12.16%; maximum drawdown -33.11%; 52 closed trades; win rate 50.0%. **Trailed benchmark; not promoted.**

Cost stress (one-way bps → CAGR): 0 → 9.23%, 5 → 9.10%, 10 → 8.97%, 15 → 8.84%, 20 → 8.71%, 30 → 8.45%, 50 → 5.96%.

Rolling window counts: 3m: 35, 6m: 34, 12m: 32, 36m: 24, 60m: 16.

## 13. Missing results are not invented

No new India PIT baseline/neighbor/cost runs were possible from this checkout: required history and membership were absent. The user's previous India performance figures were not reproduced. No new blind test was declared after viewing results. No forward-paper observations, broker cash reconciliation, latency benchmarks, provider uptime or sandbox success are claimed. Taxes and separate research fee/spread/slippage components remain null; the zero-cost run is a gross comparator. The tests use synthetic fixtures only to check software behavior.

## 14. Tests and validation

- Initial baseline: 34 tests passed.
- Final: **48 tests passed** on Python 3.13.5, including provider parsing, input validation, PIT membership, no look-ahead, fee/slippage, stale/divergent quotes, partial fills, cash accounting, reconciliation blocking, deterministic replay, concurrent replay, transaction rollback, drawdown/cooldown, identity reuse, immutable storage, config checks, dashboard generation and Streamlit rendering for all three phases.
- `ruff check .`: passed.
- `python -m compileall -q src scripts app.py`: passed.
- `python -m qts.runtime --once` with production-paper and realtime-paper configs: passed; explicitly heartbeat-only, not live engine certification.
- `python -m qts.dashboard`: passed.
- `git diff --check`: passed.
- Browser: local page opened, screenshot reviewed, US and Global navigation verified. Streamlit AppTest covered India/US/Global. No authenticated provider integration, Docker build, remote CI run or deployment was executed.

## 15. Dashboard changes

Pages and Streamlit read the same three-phase snapshot. Prominent paper/research, provider/data mode, internal execution, transmission-disabled and reconciliation panel; holdings and legacy fills; new order lifecycle records; portfolio curve; phase risk/health; independent promotion requirements; actual ETF diagnostic windows and cost stress on Pages. Missing metrics explicitly show Not measured. Official market state is UNKNOWN until a session source is connected. Quotes are not labelled realtime from a desired config alone. Full metrics are expandable; keyboard-accessible controls and narrow-screen CSS included.

## 16. Known limitations / work still outstanding

1. Authenticated WebSocket collectors and unattended signal-to-order scheduling are not implemented. REST adapters and trusted input-bundle execution are tested locally; successful authentication, quote entitlements and source agreement still need real accounts.
2. Historical India PIT membership, security master, delistings, corporate actions and adjusted TRI are missing. No robust India rerun can be claimed. ETF fixed-universe results include ex-post universe selection and are screening only.
3. Official holiday/half-day/halt and corporate-action ingestion is not connected. Bundle booleans are collector attestations, not independently verified exchange facts. Never automate those values as unconditional true.
4. Legacy ledger migration/reconciliation is deliberately not performed. The new durable broker starts a separate account; validate official split/dividend entitlements before importing balances. Buy fees are tracked separately from entry price and allocated on sells for realized P&L.
5. US/global provider transports, IBKR paper reconciliation and authenticated sandbox lifecycle tests remain outstanding. No active country-level broker accounts or real-capital pilot exists.
6. Research uses adjusted fractional total-return units, zero interest on cash, aggregate trading costs and abort-on-missing-held-price semantics. It does not model tax, market impact, auction depth or official delisting proceeds. Equity drift may exceed target weights; benchmark-relative and drawdown results fail promotion anyway.
7. Automated durable run/error telemetry, dynamic dashboard quote-age refresh, full live metrics and automatic evidence aggregation are not complete. Snapshot quote age is calculated at generation. Reconciliation PASS is scoped to internal paper account versus internal fill ledger, not an external broker statement.
8. Paper order execution is immediate-or-cancel; no HFT queue simulation or asynchronous resting-order engine. Displayed size is a conservative cap, not guaranteed available liquidity. SQLite requires one persistent host; distributed deployment is not supported.

## 17. Accounts and credentials needed manually

Eligible Upstox account/API app + separate Sandbox app; FYERS account/API app; Alpaca paper account; IBKR paper account and any required data subscriptions. Environment variables: `UPSTOX_ACCESS_TOKEN`, `UPSTOX_SANDBOX_TOKEN`, `FYERS_APP_ID`, `FYERS_ACCESS_TOKEN`. US/global transport credential configuration is pending its implementation. Do not commit secrets or place tokens in public Pages. Provider/residency/product eligibility and raw quote redistribution rights must be checked on the actual account.

## 18. Deployment remaining

Review this diff and operational retirement of old cron execution first. No commit/push was performed. After review, commit/push the validated source, let remote CI run, then deploy Pages using the existing workflow. The published site remains unchanged in this task. Broker-data paper execution requires a durable host, authenticated collectors, official data mapping/actions, recovery tests and phase-specific paper activation. Neither a config label nor the word “live” bypasses promotion.

## 19. Current Git status

Branch `main`, based on the cloned revision above. All changes are local and unstaged; no new commit or push. Generated historical datasets and execution databases are ignored. Exact status at report generation:

```
 M .github/workflows/ci.yml
 M .github/workflows/paper-trader.yml
 M .github/workflows/us-paper-trader.yml
 M .gitignore
 M README.md
 M app.py
 D artifacts/phase25_results.json
 M configs/paper-trader.json
 M configs/production-live.yaml
 M configs/production-paper.yaml
 M configs/realtime-paper.yaml
 M configs/staging.yaml
 M docs/index.html
 D scripts/phase25_research.py
 M src/qts/automation.py
 M src/qts/broker.py
 M src/qts/config.py
 M src/qts/execution.py
 M src/qts/paper.py
 M src/qts/runtime.py
 M src/qts/safety.py
 M src/qts/upstox.py
 M src/qts/us_automation.py
 M tests/test_automation.py
 D tests/test_phase25.py
 M tests/test_safety.py
?? DATA_ARCHITECTURE.md
?? PROVIDERS.md
?? REBUILD_REPORT.md
?? archive/rejected_rotation/README.md
?? archive/rejected_rotation/phase25_research.py
?? archive/rejected_rotation/phase25_results.json
?? archive/rejected_rotation/test_phase25.py
?? artifacts/rebuild_results.json
?? configs/phases.json
?? data/backtests/.gitkeep
?? data/corporate_actions/.gitkeep
?? data/features/.gitkeep
?? data/live_cache/.gitkeep
?? data/normalized/.gitkeep
?? data/schemas.json
?? data/security_master/.gitkeep
?? data/universe_membership/.gitkeep
?? scripts/download_research.py
?? src/qts/dashboard.py
?? src/qts/fyers.py
?? src/qts/paper_broker.py
?? src/qts/planning.py
?? src/qts/platform.py
?? src/qts/research.py
?? src/qts/storage.py
?? tests/test_platform.py
?? tests/test_research_pipeline.py
```

## 20. Recommended next step

Review the local diff, then provide access to audited India PIT data and configure Upstox/FYERS accounts so the read-only adapters can be authenticated and compared. Build the official session/action collector and durable scheduled input-bundle workflow before restarting unattended paper execution. Continue to reject strategy promotion unless unseen-period and forward-paper evidence passes the independent gates.
