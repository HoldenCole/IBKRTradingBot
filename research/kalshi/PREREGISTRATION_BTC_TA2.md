# Bitcoin technical signals through Kalshi, round 2: pre-registration (entry 111)

Written 2026-11-27 before any of the signals below was scored. Nothing below may change after results are seen.

User direction: try fading breakouts and the hourly contracts, then other technical options; do not give up on
expressing a bitcoin view through Kalshi binaries.

Common to all: Binance BTCUSDT 1-minute closes, 2020 to November 2026 (entry 110's data); signals use only closes
at or before the window's start; the binary's break-even hit rate is about 53% at a 50c price with the 2c fee and
1c slippage. The Binance gate is a hit rate of at least 53.5% in both 2020-2022 and 2023-2025, with at least
1,000 bets in each. A signal that passes the Binance gate goes to a Kalshi check at actual prices, March to
November 2026, which passes if the mean return per dollar is above zero with a t-statistic of at least 2
(clustered by day) AND is positive in September-November 2026 (the market has been catching up; entry 110).

## A. Breakout fade on the 15-minute contract

B1: fade a 20-bar breakout of 15-minute closes (close above the prior 20 closes' high, bet down; below the low,
bet up). This is entry 110's T7 reversed; its Binance hit rates (57.5% / 56.4%) were seen in entry 110, so it goes
straight to the Kalshi check (buy at the last trade within 60 s before 1 minute into the window, plus 1c and fee).

## B. The hourly contract (KXBTCD, "above strike K at the hour's end")

Hourly windows from :00 to the next :00 (UTC). Outcome proxy on Binance: up if the close at the hour's end is at
or above the close at its start.

- H1 fade a Bollinger(20, 2) extreme of hourly closes.
- H2 fade a Bollinger(20, 2) extreme of 15-minute closes, measured at the hour's start, for the next hour.
- H3 fade an RSI(14) extreme (below 25 / above 75) of hourly closes.

Kalshi check for a passer: at 2 minutes after the hour, take the hour's market whose strike is nearest to the
Binance price times (1 - 0.00055) (entry 109's measured basis); buy YES to bet up or NO to bet down, at the last
trade within 120 s before the checkpoint, plus 1c and fee; hold to the hour's end.

## C. Other technical options for the 15-minute contract

- C1 stretched move: the previous 15-minute return divided by (1-minute volatility of the last 60 minutes x
  sqrt(15)); beyond +2, bet down; below -2, bet up.
- C2 stochastic extreme: %K(14) of 1-minute closes (close relative to the 14-minute closing range) below 5, up;
  above 95, down.
- C3 runs: three 15-minute windows in a row up, bet down; three down, bet up.
- C4 last-minute shock: the last 1-minute return beyond 3 standard deviations (last 60 minutes), fade it.
- C5 agreement: entry 110's Bollinger fade and RSI(14) extreme fade both signal, in the same direction.

Kalshi check for a passer: as in A.

## Reported

Every signal's hit rate by period and by year, bets per day, and for each Kalshi check the return per dollar by
quarter of 2026 and at 2c slippage. A pass goes to a paper bot; real money only after that and the investor's
approval.
