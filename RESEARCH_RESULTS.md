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
