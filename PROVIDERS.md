# Provider matrix — official documentation checked 7 September 2026

Pricing and eligibility are account-specific. No credentials were used and no brokerage integration was authenticated during this rebuild. The suitability column is this project's assessment, not a provider claim. A market-data entitlement is not permission to redistribute raw quotes on public Pages.

| Phase / provider | Live data / historical | Paper or sandbox / order API | Streaming | Cost and access limits | Project fit |
|---|---|---|---|---|---|
| India — Upstox | Full quotes and candles | Sandbox covers documented order endpoints; separate token; real order APIs exist | V3 WebSocket, Protobuf; mode/connection quotas | API advertised free; Upstox account/app/auth needed; verify current entitlements | Primary India feed; internal fills; separate sandbox payload test |
| India — FYERS | Live and historical APIs | Order API; no official general paper sandbox verified in reviewed pages | Data WebSocket | API advertised free; FYERS account/app required | Independent validation; missing validation blocks trades |
| India — Angel One SmartAPI | Market quotes and historical candles | Order API; no official paper sandbox verified | WebSocket; connection limits | API marketed free; brokerage account and authentication required | Alternative validation/feed adapter, not installed here |
| India — Zerodha Kite | Realtime and historical data | Order API; no paper simulator assumed | WebSocket | Official forum states ₹500/month for data APIs; account/app required | Paid alternative, not necessary for initial paper core |
| US — Alpaca | Free Basic realtime IEX only; historical data feed-specific | Free paper-only account; separate paper keys/endpoints; live eligibility differs | IEX WebSocket; consolidated SIP requires appropriate plan | Paper-only sign-up available globally; IEX is not consolidated NBBO | Low-cost ETF research/paper feed; independent validator still required |
| US / Global — IBKR | Exchange-dependent data and historical API, with pacing and entitlements | Paper TWS/IB Gateway or Web API; simulator limitations | TWS callback streaming; Web API WebSocket | Most API securities require top-of-book subscription; live funded account needed for paid subscriptions; regional product permissions | Broad-market validation and eventual paper account testing; not universally free |
| US / Global — Yahoo convenience feed | Historical adjusted OHLC / potentially delayed observations | No brokerage sandbox or order API used | No supported realtime integration claimed | No paid subscription used here; reliability and redistribution not guaranteed | Downloaded diagnostic research only; never used as executable realtime quotes |

Official references:

- [Upstox API](https://upstox.com/developer/api-documentation/), [full quote contract](https://upstox.com/developer/api-documentation/get-full-market-quote/), [sandbox](https://upstox.com/developer/api-documentation/sandbox/), [V3 market feed](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/).
- [FYERS API](https://fyers.in/products/api), [data WebSocket](https://support.fyers.in/portal/en/kb/articles/how-can-i-use-the-data-websocket-in-api-v3-to-access-real-time-data).
- [SmartAPI free-tier FAQ](https://smartapi.angelone.in/faq), [SmartAPI market data documentation](https://smartapi.angelone.in/docs/MarketData).
- [Kite data API pricing statement](https://kite.trade/forum/discussion/15603/is-order-placement-market-limit-etc-and-gtt-gtt-oco-orders-free).
- [Alpaca paper trading](https://docs.alpaca.markets/us/docs/paper-trading), [market data plans](https://docs.alpaca.markets/us/docs/about-market-data-api), [IEX/SIP distinction](https://docs.alpaca.markets/us/docs/market-data-faq).
- [IBKR API data subscriptions](https://www.interactivebrokers.com/docs/general/market-data-subscriptions/introduction), [requesting data](https://www.interactivebrokers.com/campus/trading-lessons/requesting-market-data/), [API documentation](https://www.interactivebrokers.com/campus/ibkr-api-page/).

For an Ireland-based account, confirm provider residency/KYC eligibility and ETF product permissions directly; US-domiciled ETFs used as research proxies are not a promise of retail purchase eligibility. There is no recommendation to route real orders.

## Accounts to create manually

India: eligible Upstox trading account + API app + separate Sandbox app, and FYERS account/API app. Set `UPSTOX_ACCESS_TOKEN` and `UPSTOX_SANDBOX_TOKEN` only in environment/secrets. FYERS streaming integration is still to be wired and authenticated.

US/global: Alpaca paper-only account for IEX observations, plus IBKR paper credentials and relevant exchange subscriptions if using it as validator. Authenticate using each provider's supported flow. Never paste tokens into the dashboard or commit them. The current code has read-only Upstox full-quote and FYERS depth adapters; other live provider transports remain integration work. FYERS requires `FYERS_APP_ID` and `FYERS_ACCESS_TOKEN`; its REST depth freshness conservatively uses last-trade time. See the [official FYERS market-data reference](https://github.com/FyersDev/fyers-skills/blob/master/skills/fyers-trading/references/market-data.md).

## Architecture sources

- [LEAN reality models](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/key-concepts): explicit fee, fill and slippage assumptions rather than equating a signal with a fill.
- [NautilusTrader architecture](https://nautilustrader.io/docs/latest/concepts/architecture/): common domain events, separate environment/execution boundaries and recovery.
- [vectorbt](https://vectorbt.dev/): bounded vectorized signal research; screening is not execution realism.
- [Zipline Reloaded](https://github.com/stefan-jansen/zipline-reloaded): dated asset identity, data bundles and exchange-session handling.

These informed design choices; no source code or new framework dependency was copied. Check the exact upstream license/version before any future code reuse.
