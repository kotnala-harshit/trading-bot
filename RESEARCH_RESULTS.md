# Indian Equity Strategy Research

## Phase 2 US equities baseline — 1 September 2026

Status: **research completed; paper activation remains locked**.

The baseline used 31 current liquid US large caps, adjusted Yahoo OHLC history, five holdings, a top-ten retention buffer, 63-session risk-adjusted momentum, 60-session reviews, 20% volatility targeting, next-open execution, and 0.05% one-way costs. Parameters were developed on the first five years and checked once on the untouched later five years.

The holdout returned 12.50% annualized versus 12.46% for adjusted SPY. Maximum drawdown was -20.29% versus -24.50%, and 55.22% of 67 closed trades were profitable. This suggests modest risk reduction but no meaningful demonstrated excess return. Because the fixed current shortlist has survivorship bias and the model does not yet fully account for investor-specific dividend withholding, tax, or INR currency effects, it is not promoted to paper trading.

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

### Circuit-breaker correction

The forward paper implementation originally used a 5% portfolio drawdown stop with a 28-day cooldown. A historical replay that included this operational rule found it was too sensitive: in the later five-year sample it reduced annualized return from 14.68% to 4.14% and completed-trade win rate from 66.23% to 45.00%. Hard Nifty 200-day exits and a proposed 70/30 tactical sleeve also underperformed.

The paper circuit breaker is therefore widened to an emergency-only 20% threshold while retaining the 28-day cooldown, top-five/top-ten holding buffer, 60-session reviews, anomaly veto, costs, corporate-action handling, and live-trading lock. In the later five-year replay the 20% stop did not fire; in the earlier sample it improved maximum drawdown modestly from -37.03% to -35.41% while annualized return changed from 8.55% to 8.27%. This is a safety calibration, not evidence that future losses are capped at 20%.

### Rejected short-term 5% risk-budget experiment

A separate 1 September 2026 search tested point-in-time Nifty 50 constituents over ten years. The development period was September 2016 through August 2021 and the later five years were left untouched until selection. The predefined candidates varied 20/63-session momentum, risk-adjusted momentum, three/five-stock portfolios, 5/10/20-session reviews, 5/8/12% trailing exits, and 10/15/20% profit-taking exits. Each candidate included a 5% calendar-year portfolio circuit breaker, next-open execution, adjusted prices, current Groww delivery brokerage and statutory charges, sell-side DP charges, and a conservative 20.8% deduction from profitable short-term disposals for tax and cess.

The selected development configuration used five stocks, 63-session risk-adjusted momentum, 20-session reviews, an 8% trailing exit, and 10% profit-taking. It returned 6.42% annualized in development but failed the untouched later period at -4.55% annualized, -25.01% maximum drawdown, 32.26% completed-trade wins, and no double-digit calendar years. The ten-year combined result was only +0.63% annualized. Costs and conservative tax deductions in the holdout were approximately ₹43,183 and ₹80,592 respectively. Overnight gaps also breached the intended 5% calendar-year boundary; the worst holdout calendar year was -6.95%.

This model is rejected and was not promoted. A 5% loss ceiling cannot be guaranteed with individual equities because stop orders can fill below their trigger after gaps. The requested combination of a hard 5% downside boundary and double-digit returns every calendar year was not supported by this historical evidence.

### Rejected exponentially weighted replacement

An additional test on 1 September 2026 gave recent observations greater weight using exponentially weighted returns, volatility, and distance from exponential moving averages with 10/20/40/60-session spans. Candidate parameters were selected only on September 2016–August 2021, using the same point-in-time Nifty 50 membership, adjusted daily prices, five holdings, top-ten retention buffer, next-open execution, and 0.10% one-way research cost as the deployed ranking benchmark. The selected candidate ranked 20-session EMA distance adjusted for exponentially weighted volatility and reviewed every 60 sessions.

The EMA candidate improved the combined ten-year annualized result from 16.21% to 16.76%, improved combined completed-trade wins from 58.39% to 60.53%, and modestly reduced maximum drawdown from -35.21% to -33.47%. It nevertheless failed the untouched later five-year comparison: annualized return was 12.45% versus 14.68%, completed-trade wins were 53.42% versus 66.23%, and maximum drawdown was -22.47% versus -18.70%. Its rolling three-month profitable rate was 59.18% versus 66.01%, and it beat the Nifty price index in 50.04% versus 60.38% of rolling three-month windows. The EMA model is therefore retained only as a research reference and was not promoted.

### Corporate-action total-return recheck

The preferred rules were rerun on 31 August 2026 using Yahoo adjusted OHLC history and, separately, raw price-only history. Adjusted history represents dividend/split effects and avoids false momentum signals around splits and bonus-style ratio events.

| History treatment | 5y annualized | 5y win rate | 5y drawdown | 10y annualized | 10y win rate |
|---|---:|---:|---:|---:|---:|
| Corporate-action adjusted | +14.31% | 66.23% | -18.70% | +16.21% | 58.39% |
| Raw price only | +7.32% | 60.24% | -22.23% | +13.50% | 56.38% |

The comparison confirms that corporate-action treatment materially changes both ranking and measured performance. It does not isolate dividends from split corrections, and Yahoo is a convenience source rather than an official corporate-action record. Forward paper events are therefore deduplicated and auditable, but any eventual live workflow would require reconciliation to NSE/company notices.

### Volatility-target drawdown experiment — 1 September 2026

The existing buffered strategy was retested with four predefined controls: broader eight-stock diversification, a Nifty 200-day EMA exposure filter, progressive portfolio brakes, and 20% annualized Nifty volatility targeting with a 50% minimum exposure. The combined controls reduced drawdown but damaged the untouched later-five-year return; diversification, the EMA filter, and progressive brakes were therefore rejected.

Volatility targeting alone preserved the five-stock/top-ten-buffer selection and trade win rate. In the untouched later five years it changed annualized return from 13.55% to 13.03%, maximum drawdown from -19.01% to -17.76%, and worst rolling three-month return from -17.57% to -13.02%. The proportion of profitable rolling 12-month periods increased from 87.18% to 87.59%, and the proportion beating Nifty increased from 67.04% to 70.30%. In the earlier five-year development sample it reduced maximum drawdown from -36.90% to -30.02% and worst rolling three-month return from -27.17% to -19.68%, while annualized return changed from 17.38% to 14.75%.

This isolated control is promoted to paper observation. It does not eliminate drawdowns, guarantee a loss boundary, or authorize live orders.
