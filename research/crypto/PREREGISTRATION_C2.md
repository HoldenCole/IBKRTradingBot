# Crypto C2: daily trend following on liquid coins: pre-registration (entry 102)

Written 2026-11-26 before any result. Nothing below may change after results are seen.

The method is Zarattini, Pagani and Barbon, "Catching Crypto Trends" (Swiss Finance Institute paper 25-80,
version of 9 April 2025, sample January 2015 to 19 March 2025), read from the paper itself.

## The method as published

- Donchian channel on closes over n days: Up = max close, Down = min close, Mid = (Up + Down) / 2.
- For each n in {5, 10, 20, 30, 60, 90, 150, 250, 360}: go long when the close equals Up(n). The trailing stop
  starts at Mid(n) on entry and each day becomes max(prior stop, Mid(n) at that close); exit on a close at or
  below the stop. Long only.
- Size: w = min(25% / sigma, 200%) while long, sigma = annualised 90-day volatility of daily returns.
- Combo: the equal-weight average of the nine weights. Returns use the prior day's weight.
- Costs on traded notional; a 20% rebalance threshold applies only to volatility-driven size changes (a new entry
  or a stop exit trades at once). Headline: 10 bp a side.
- Portfolio: at each month end, coins listed for at least 365 days, not stablecoins, wrapped tokens or NFT
  collectibles, with a median daily volume of at least $2 million over the prior 30 days, ranked by that median;
  the top B form next month's universe. Each gets 1/B of the capital at the start of the month and runs the Combo
  inside its share. A coin leaves when its 30-day median volume falls below $1 million or its median daily price
  change is below 0.5%.
- Published results, top 20, January 2015 to 19 March 2025, net of 10 bp: CAGR 18%, volatility 9%, Sharpe 1.57,
  maximum drawdown 11%. Bitcoin alone, gross: CAGR 30%, volatility 17%, Sharpe 1.58, maximum drawdown 19%.

## Part A: implementation check (not a gate on the idea)

Bitcoin only, Coinbase BTC-USD daily closes, 2015-01-01 to 2025-03-19, no costs. The implementation is accepted
if CAGR is within 5 points and Sharpe within 0.3 of the published 30% and 1.58. Data differ (Coinbase alone
versus CoinMarketCap's aggregate), so a small gap is expected. A larger gap means a bug to find, not a parameter
to change.

## Part B: the portfolio on Binance spot

- Data: Binance spot daily candles for every USDT pair in the public archive, including delisted pairs.
  Volume is the quote (USDT) volume. Binance starts in August 2017, so the first eligible month is September
  2018. Excluded: stablecoins and fiat-pegged tokens, wrapped tokens, and leveraged tokens (UP, DOWN, BULL, BEAR).
- Universe sizes B in {5, 10, 20}. A month with fewer eligible coins than B leaves the spare shares in cash.
- Costs: 10, 25 and 50 bp a side. 50 bp is the realistic US retail level (Kraken Pro entry-tier taker plus
  spread); 25 bp is maker orders.
- Sizing variants:
  - the paper: 25% target, cap 200% per lookback;
  - spot-feasible, higher risk: 50% target, cap 100%;
  - spot-feasible, highest risk: 100% target, cap 100%.
  The spot-feasible variants also cap total exposure at 100% of the account (no borrowing).
- Windows: replication, 2018-09-01 to 2025-03-19; post-publication, 2025-03-20 to the last close
  (data the authors did not have).
- Benchmarks: bitcoin buy and hold; equal-weight buy and hold of the same top-B universe, rebalanced monthly.

## Gates (the paper's sizing, B = 20, 25 bp)

1. Replication window Sharpe of at least 1.0.
2. Sharpe above 0.5 in each half of the replication window: 2018-09 to 2021-12 and 2022-01 to 2025-03-19.
3. Post-publication: net return above zero and Sharpe of at least 0.5. About 19 months is too short to confirm
   an edge; this gate can only catch a collapse.

Passing all three makes the design a candidate for paper trading. The higher-risk variants and the smaller
universes are reported with every gate's numbers, for the account-size and leverage decision.

## Disclosed limits

Binance's archive covers coins listed on Binance only, from 2017. Delisted pairs remain in the archive, but coins
never listed there are missing. A US person cannot trade on Binance; Kraken lists fewer coins and some are not
available in every state.
