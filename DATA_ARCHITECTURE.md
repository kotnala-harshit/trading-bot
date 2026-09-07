# Data contracts

All timestamps must have UTC offsets for quotes/orders. Daily research dates are exchange session dates. Treat publication time (`known_at`) separately from effective dates. Half-open identity and membership intervals prevent ticker reuse from silently joining companies.

- `data/raw/`: immutable SHA-256-addressed original response bytes. Exclusive creation; a repeat checks bytes. Never overwrite a response. Download provenance records retrieval time and content hash separately.
- `data/normalized/`: reproducible provider transformations. Research OHLC uses adjusted-close/raw-close factors on every OHLC field; raw close and raw traded value remain separate. These are total-return units, not tradable share prices. Never credit dividends again in an adjusted-price backtest. A raw-share paper ledger instead needs official splits/dividends and entitlements.
- `data/security_master/`: `security_id, provider, symbol, valid_from, valid_to, known_at, exchange, currency, isin, source`. Resolve exactly one dated identity; missing/ambiguous mappings block use. ETF download symbols are provisional diagnostic identities, not an audited master.
- `data/universe_membership/`: `security_id, effective_from, effective_to, known_at, source`. Include exits and delistings; publication time cannot be inferred from today's constituent list. Overlapping intervals are rejected.
- `data/corporate_actions/`: `event_id, security_id, effective_at, known_at, kind, numerator, denominator, cash_amount, currency, source`. Official verification is required before paper execution; live engine does not yet automate entitlement ingestion.
- `data/live_cache/`: short-lived primary/validation quotes, exchange timestamp, receipt timestamp, bid/ask/size and provider. Missing sizes or timestamp block execution. Never substitute request receipt time for exchange quote time.
- `data/features/`: security ID, decision time, data cutoff, model/config hash, rank and score; derive only from completed sessions.
- `data/backtests/`: input hashes, predeclared parameters, windows, cost scenarios, curve and trade evidence. Large datasets/results are ignored by Git.
- `runtime/ledgers/<phase>.sqlite`: authoritative SQLite account, intended rebalance and fill tables; one ACID transaction per batch, deterministic primary keys and independent ledger replay reconciliation.
- `runtime/orders/`, `runtime/reconciliation/`: optional diagnostic exports; never alternate sources of truth. The database owns order lifecycle and reconciliation evidence.
- `runtime/<phase>_platform.json`: replace-atomically dashboard snapshot, rebuildable from execution state. Existing JSON/CSV ledgers remain legacy evidence and are not silently imported as verified balances.

## Input validation

Normalized research CSV: `date,security_id,open,close,raw_close,traded_value,quality_ok`; optional raw OHLC and volume retained. Finite positive prices, unique security/session, nonnegative liquidity, adequate history, last-session coverage and quality flags are required. A missing held price aborts research rather than fabricating a delisting sale. Cash receives zero interest; withholding and country-specific tax are not guessed.

## Reproduce ETF diagnostics

```
PYTHONPATH=src python scripts/download_research.py --phase us
PYTHONPATH=src python -m qts.research --phase us --prices data/normalized/us/prices.csv --membership data/normalized/us/diagnostic_membership.csv --benchmark data/normalized/us/benchmark.csv --development-end 2021-08-31 --validation-end 2023-08-31 --output data/backtests/us_diagnostic.json
```

Replace `us` with `global` for the 13-country basket. These are today's selected ETF baskets: their generated fixed membership is explicitly **not historical stock-index membership**. They are unsuitable for promoting a PIT stock strategy. India needs licensed/audited membership, identity, delisting and total-return data before comparable research can run.
