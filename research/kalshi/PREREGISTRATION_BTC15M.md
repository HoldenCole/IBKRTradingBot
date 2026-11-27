# Kalshi 15-minute bitcoin up/down: fair value against market prices: pre-registration (entry 109)

Written 2026-11-27 before any market price was compared with a fair value. Nothing below may change after results
are seen.

User direction: bitcoin up/down binary contracts, short term only.

## The contract

KXBTC15M: one market per 15-minute window. YES pays $1 if the average of the CF Benchmarks BRTI over the 60
seconds before the window's close is at least its average over the 60 seconds before the window's open (the
market's floor_strike). Fee: Kalshi's general taker schedule, 0.07 x p x (1 - p) per contract rounded up to the
cent (2 cents near 50c). Liquidity: median 169,000 contracts per window in March 2026, 3.9 million in November.

## Sample

Development: windows closing 2026-03-01 to 2026-08-31 (the months with a median above 100,000 contracts a window).
Hold-out: 2026-09-01 to 2026-11-26, opened once and only if every development gate passes. The Kalshi API allows
about two requests a second, so a random sample is used: 2,000 development windows and, if opened, 1,000 hold-out
windows, drawn with seed 20261127.

## Fair value

At checkpoint m minutes after the window opens, m in {1, 5, 10}:

- S = Binance BTCUSDT 1-minute close of the minute ending at the checkpoint, times (1 + b), where b is the median
  of (settlement value / Binance close of the minute ending at the window's close - 1) over the previous 96 settled
  windows (the USD-USDT basis, measured from data before the window).
- K = the window's strike (the BRTI average at the open, from the market itself).
- sigma = standard deviation of Binance 1-minute log returns over the 60 minutes before the checkpoint.
- tau = 15 - m - 0.5 minutes (the settlement is a 60-second average).
- Fair probability of YES = N( ln(S / K) / (sigma x sqrt(tau)) ).

## Price, trade rule and return

Price = the YES price of the last Kalshi trade at or before the checkpoint, required to be within the 60 seconds
before it. Fill = price + 1 cent (YES) or (1 - price) + 1 cent (NO). Buy YES if fair - fill - fee >= 0.03; buy NO
if (1 - fair) - fill - fee >= 0.03. Held to settlement (at most 14 minutes). Equal dollar stake per trade.
Return per dollar = (payout - fill - fee) / (fill + fee).

## Gates (development, all checkpoints pooled)

1. At least 500 trades.
2. Mean return per dollar above zero with a t-statistic of at least 3, standard errors clustered by day.
3. Positive in each half (March-May and June-August).
4. Still positive with 2 cents of slippage.

Reported for each checkpoint, and the calibration of the fair value and of the market price against outcomes.
Hold-out: mean return per dollar above zero, one-sided p below 0.05. A pass goes to a live paper bot; real money
only after that and the investor's approval.

## Disclosed limits

The last trade price is not a quote: a live order competes with fast bots and may fill worse. Binance BTCUSDT
stands in for the BRTI, corrected by the measured basis.
