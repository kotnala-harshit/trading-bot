# Production readiness

Paper/staging deployment is ready when CI, preflight, dashboard health, persistent heartbeat, and IBKR paper connectivity pass. Real-money promotion remains blocked until every item below has dated, reviewable evidence.

## Data and research gate

- Licensed real MES contract-level data is stored outside Git.
- Timezone, session calendar, OHLCV, missing bars, duplicates, and outliers pass validation.
- Roll policy is explicit and avoids look-ahead; research and executable contract series are distinct.
- Strategy thesis and parameters were written before final out-of-sample evaluation.
- Walk-forward, cost/slippage stress, parameter stability, permutation, PBO/selection-bias, and Deflated Sharpe checks are complete.
- Results replicate on held-out periods and related instruments without cherry-picking.

## Paper execution gate

- At least 30 trading days and a representative trade sample are reconciled.
- Modeled versus actual fills, commission, slippage, rejected orders, reconnects, partial fills, and session boundaries are reviewed.
- Duplicate-order prevention, order-rate limit, max position, daily-loss limit, stale-data stop, and kill switch have fault-injection tests.
- Restart recovery reconciles broker state before new orders.

## Operational gate

- Named operator, alert channel, backup operator, incident runbook, and rollback owner exist.
- Secrets come from the deployment secret store and have least privilege.
- Logs are durable but redact account IDs, tokens, and personal data.
- Dashboard access is private and protected by the host's authentication.
- A release tag and immutable container digest are recorded.

## Live promotion gate

The committed `configs/production-live.yaml` intentionally has `dry_run: true` and `autonomous_order_transmission: false`. Changing both is necessary but not sufficient. The runtime separately requires:

```text
TRADING_MODE=live
LIVE_TRADING_ENABLED=true
LIVE_TRADING_ACK=I_UNDERSTAND_REAL_MONEY_CAN_BE_LOST
IBKR_ACCOUNT_CONFIRMED=true
```

Do not store those acknowledgements in Git. Promotion must be reviewed out of band, start at one MES contract, occur while supervised, and retain a tested manual broker-side cancel/flatten procedure.

