# Crypto C3: bitcoin signals, traded short-term and levered in bitcoin and altcoins: pre-registration (entry 103)

Written 2026-11-26 before any result. Nothing below may change after results are seen.

User direction: short-term, highly levered positions. Coins move together, so read the signal from bitcoin and
trade an altcoin. Objective: absolute return, not Sharpe or Sortino. This is the risk account, not the
investment account.

## Instruments and US leverage limits

Traded: BTC (the control), ETH, SOL, XRP, DOGE, all available to US persons as CFTC-regulated perpetual-style
futures. Leverage caps from Coinbase Financial Markets product pages: BTC and ETH 10x, SOL and XRP 5x, DOGE 4x.
Kraken (Bitnomial) also lists these coins for US users; its leverage limits were not confirmed.

## Data

Binance USD-M perpetual hourly candles (UTC) and 8-hour funding rates, January 2020 to October 2026, as a proxy
for the US contracts (which have short histories). Development: 2020-01-01 to 2023-12-31, in two eras (2020-21
and 2022-23). Hold-out: 2024-01-01 to the end of the data, opened once and only for a signal that passes every
development gate.

## Signals (computed on BTC only, at the close of an hourly bar; a trade enters at that close)

sigma = standard deviation of BTC hourly returns over the prior 720 hours.

- S1 impulse 1h, hold 4h: BTC's last-hour return above +2 sigma, go long; below -2 sigma, go short. Exit after 4 hours.
- S2 impulse 1h, hold 1h: the same, exit after 1 hour (the fast lead-lag version).
- S3 impulse 4h, hold 24h: BTC's last-4-hour return above +4 sigma (2 x the 4-hour sigma), long; below -4 sigma, short.
  Exit after 24 hours.
- S4 4-hour breakout: on 4-hour bars, a close above the prior 20-bar high, long; below the prior 20-bar low, short.
  Exit when the close crosses the opposite 10-bar extreme, or after 72 hours.
- S5 4-hour dip and rip: on 4-hour bars, BTC RSI(2) below 10, long; above 90, short. Exit after 24 hours.
- S6 daily trend: long while the entry-102 Combo target on BTC daily closes is above zero, flat otherwise. Long only.
  Checked at each daily close.

Each signal trades each instrument separately, one position at a time; a signal that fires while a position is
open is ignored. Short positions are allowed (the no-short rule covers the broad US stock market only).
30 trials: 6 signals x 5 instruments.

## Costs

10 bp a side on the notional, plus actual funding at each 8-hour mark while held (longs pay positive funding,
shorts receive it). Stress: 20 bp a side.

## Gates (development data, 1x, 10 bp)

1. At least 200 trades (S6: at least 20).
2. Mean net return per trade above zero in both eras (S6: CAGR above zero in both eras).
3. t-statistic of the mean net return at least 2.5, and the Holm-Bonferroni adjustment across all 30 trials
   below 5%. S6 is judged on gates 1, 2 and 4 only.
4. Still positive at 20 bp a side.

A passer has its hold-out opened once and passes if the mean net return per trade is above zero (one-sided
p < 0.05). For S6, the hold-out CAGR must be above zero.

## Leverage and ruin (reported for every trial, decisive only for passers)

The account puts its whole equity up as margin for each position, at leverage L in {1, 2, 3, 5, 10}, capped at
the instrument's US limit. A position is liquidated if the hourly high or low moves against it by 1/L - 0.5%
from entry. A liquidation loses (1 - 0.005 L) of the equity at risk. Reported: CAGR, final multiple, maximum
drawdown, number of liquidations, and the growth-optimal leverage. Ruin means equity falling below 10% of its
starting value.

## Reported comparison: is the altcoin the better instrument?

For each signal, the altcoin trade's mean net return divided by its standard deviation, against BTC's own. The
idea that bitcoin leads and altcoins follow implies the altcoin ratio is higher. If it is not, the same signal
traded in bitcoin at higher leverage is the better use of it.
