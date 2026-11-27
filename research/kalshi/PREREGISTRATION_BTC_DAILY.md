# Bitcoin reversal signals through Kalshi's daily bitcoin contract: pre-registration (entry 114)

Written 2026-11-27 before any daily signal was scored. Nothing below may change after results are seen.

User direction: try the daily bitcoin contracts with the same signals (the reversal family of entries 110-113),
including profit targets.

## The contract

KXBTCD's 17:00 New York event: opens 17:00 the day before, settles on the CF Benchmarks index average over the 60
seconds before 17:00. Strikes about $250-500 apart; about 3.7 million contracts a day in late 2026.

## Binance gate (2020-2025)

Daily windows from 17:00 New York to 17:00 the next day (DST-aware). Outcome proxy: up if the Binance close at the
end is at or above the close at the start. Signals at the window's start:

- D1 fade a Bollinger(20, 2) extreme of 17:00 daily closes.
- D2 fade an RSI(14) extreme (below 25 / above 75) of 17:00 daily closes.
- D3 fade a Bollinger(20, 2) extreme of 15-minute closes, for the next 24 hours.
- D4 fade a Bollinger(20, 2) extreme of hourly closes, for the next 24 hours.
- D5 bet against the previous 24 hours.

With one bet a day at most, the gate is higher than entries 110-111: a hit rate of at least 55% in both 2020-2022
and 2023-2025, with at least 100 bets in each.

## Kalshi check (passers only), March to November 2026

At 5 minutes after the window opens, take the strike nearest the basis-adjusted Binance price; buy the signalled
side at the last trade within 5 minutes before that, plus 1c, plus the taker fee. Two exits: hold to settlement;
and profit targets +5, +10, +15c with no stop (the held side's value every 5 minutes from the fair-value model,
sold at value - 1c - fee). A passer must have a mean return per dollar above zero with a t-statistic of at least 2
(at least 3 for the target variants, which are 3 trials each) and be positive in September-November 2026.
With about one bet a day at most, the Kalshi sample is small; a large effect is needed to pass.
