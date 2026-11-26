# Kalshi: are contract prices biased enough to trade after fees? Pre-registration (entry 106)

Written 2026-11-26 before any price was compared with an outcome. Nothing below may change after results are seen.

User direction: look at prediction markets as an edge where a small account is not a handicap. The documented
candidate is the favourite-longshot bias: cheap contracts (long shots) are overpriced and expensive ones
(favourites) slightly underpriced, so buying favourites may pay after fees and buying long shots loses.

## Data (Kalshi public API, no key)

- Series list with categories. A stratified sample: up to 30 series from each category with at least 30 series,
  drawn at random with a fixed seed (20261126), excluding multivariate / combination series (tickers starting
  KXMVE).
- For each sampled series, up to 40 of its settled binary markets that closed between 2024-01-01 and 2026-11-25,
  had a result of yes or no, were open at least 48 hours, and traded at least 100 contracts.
- Price: the last trade at or before 24 hours before the close, the YES price of that trade. A market with no trade
  in its first (life - 24h) is dropped. Second horizon, reported only: the last trade at or before 1 hour before close.

## Measures

For a contract bought at price p (the YES price for YES, 1 - p for NO), the return per dollar is
(payout - p - fee) / (p + fee), payout 1 if it wins, 0 if not. Taker fee per contract: 0.07 x p x (1 - p),
rounded up to the next cent (Kalshi's general schedule); maker orders pay nothing in most series and are reported
as the no-fee case.

Calibration: realised YES frequency against price, in 5-cent buckets.

## Candidate trades (fixed now)

- K1 buy the favourite when its price is 90 to 99 cents (YES if YES >= 0.90, NO if YES <= 0.10).
- K2 buy the favourite when its price is 75 to 90 cents.
- K3 buy the long shot when its price is 1 to 10 cents (expected to lose; the control).

## Gate (taker fee, 24-hour horizon)

A candidate passes if its mean return per dollar is above zero with a t-statistic of at least 3 (standard errors
clustered by event), positive in each calendar year present (2024, 2025, 2026), and positive in at least three of
the five largest categories in the sample. Passing means worth a paper record, not a live account: the sample
is one exchange and three years, and fills at the last trade price are optimistic for thin markets.
