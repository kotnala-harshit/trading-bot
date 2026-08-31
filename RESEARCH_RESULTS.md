# Indian Equity Strategy Research

## Free-hand point-in-time factor search — 31 August 2026

Status: **rejected; not deployed**.

The experiment tested 108 predeclared, fully invested Nifty 50 portfolios. The grid covered 63-, 126-, and 252-session momentum, 12-minus-1 momentum, risk-adjusted momentum, 3/5/10-stock portfolios, 20/60-session rebalancing, and no/100-day/200-day Nifty regime filters. Trades used the next session's open, 0.10% one-way costs, and historical index membership. HDFC was excluded because complete Yahoo history was unavailable.

The strategy was selected only on 1 September 2016–31 August 2021. The later period, 1 September 2021–31 August 2026, was held untouched until selection.

### Selected development rule

- 126-session return divided by 126-session volatility
- Top 10 historical Nifty 50 members
- Rebalance every 20 sessions
- Hold cash while Nifty is below its 100-session moving average

### Results

| Period | Strategy total | Annualized | Max drawdown | Trade win rate | Nifty total |
|---|---:|---:|---:|---:|---:|
| Development (5y) | +64.85% | +10.52% | -15.38% | 51.56% | +95.25% |
| Blind holdout (5y) | -0.66% | -0.13% | -22.37% | 40.98% | +41.02% |
| Trailing 6m | -4.43% | -8.69% | -4.83% | 33.33% | -3.16% |
| Trailing 1y | -4.04% | -4.06% | -9.59% | 39.74% | -2.21% |
| Trailing 3y | +9.78% | +3.16% | -22.89% | 43.75% | +23.90% |
| Full 10y | +62.22% | +4.96% | -22.47% | 46.20% | +174.43% |

The blind holdout failed the return, benchmark, drawdown, and win-rate objectives. The gap between development and holdout is evidence of instability/overfitting. No parameters were retuned after viewing the holdout, and this model was not promoted to the paper bot.

Yahoo's convenience history and the community-maintained membership dataset are appropriate for screening, not final execution-grade validation. Returns include the stated modelled trading cost but not every Indian tax, fee, spread, or market-impact component.

## Nifty 50 return/win-rate frontier — 31 August 2026

Status: **promising paper candidate; not promoted because every acceptance window did not pass**.

The candidate ranks historical Nifty 50 constituents by 63-session return divided by 63-session volatility, holds the top five, rebalances every 60 sessions at the next open, stays fully invested, and models 0.10% one-way costs. It was preselected from the development results because it was the highest-return configuration inside the requested 12–25% annualized-return and 60–70% trade-win bands, then evaluated on the later period.

| Period | Total | Annualized | Max drawdown | Trade win rate | Nifty total |
|---|---:|---:|---:|---:|---:|
| Latest 6m | -11.29% | -21.37% | -14.50% | 40.00% | -3.16% |
| Untouched latest 1y | +11.73% | +11.77% | -14.09% | 65.00% | -2.21% |
| Latest 3y | +57.24% | +16.30% | -11.27% | 68.33% | +23.90% |
| Later 5y holdout | +64.32% | +10.45% | -16.81% | 66.00% | +41.02% |
| Full 10y | +355.59% | +16.38% | -33.85% | 62.56% | +174.43% |

The strategy reaches both target bands over three and ten years and reaches the win-rate target over one and five years. It misses the 12% return floor over one and five years, fails both targets over six months, and has a material full-period drawdown. These mixed results justify forward paper testing but not a profitability claim or live-capital promotion.

## Buffered long-hold Nifty 50 strategy — 31 August 2026

Status: **preferred forward-paper candidate; live trading remains disabled**.

This lower-turnover version ranks historical Nifty 50 constituents by 63-session risk-adjusted momentum, holds five stocks, reviews every 60 sessions, and retains an existing holding while it remains in the top ten. A stock can therefore remain invested across multiple reviews rather than being sold and repurchased automatically. The same next-open execution and 0.10% one-way cost assumptions apply.

| Period | Strategy annualized | Nifty annualized | Max drawdown | Completed-trade win rate |
|---|---:|---:|---:|---:|
| Latest 6m | -21.37% | -6.24% | -14.50% | 40.00% |
| Latest 1y | -0.73% | -2.22% | -15.47% | 46.15% |
| Latest 3y | +12.72% | +7.41% | -18.36% | 63.04% |
| Later 5y holdout | +13.78% | +7.12% | -18.70% | 66.23% |
| Full 10y | +16.31% | +10.63% | -35.21% | 58.39% |

It beats Nifty annualized over one, three, five, and ten years and exceeds a 50% trade-win rate over three, five, and ten years. It does not pass the latest six-month or one-year win-rate gate, and the ten-year drawdown remains substantial. It is retained for forward paper observation without a profitability guarantee.

### Corporate-action total-return recheck

The preferred rules were rerun on 31 August 2026 using Yahoo adjusted OHLC history and, separately, raw price-only history. Adjusted history represents dividend/split effects and avoids false momentum signals around splits and bonus-style ratio events.

| History treatment | 5y annualized | 5y win rate | 5y drawdown | 10y annualized | 10y win rate |
|---|---:|---:|---:|---:|---:|
| Corporate-action adjusted | +14.31% | 66.23% | -18.70% | +16.21% | 58.39% |
| Raw price only | +7.32% | 60.24% | -22.23% | +13.50% | 56.38% |

The comparison confirms that corporate-action treatment materially changes both ranking and measured performance. It does not isolate dividends from split corrections, and Yahoo is a convenience source rather than an official corporate-action record. Forward paper events are therefore deduplicated and auditable, but any eventual live workflow would require reconciliation to NSE/company notices.
