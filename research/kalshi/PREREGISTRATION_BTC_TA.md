# Bitcoin technical signals expressed through Kalshi 15-minute up/down contracts: pre-registration (entry 110)

Written 2026-11-27 before any signal was scored. Nothing below may change after results are seen.

User direction: do not hunt for mispricings in a liquid market; forecast bitcoin with technical analysis or other
methods, and use the Kalshi up/down contract to express the view, since its payoff can make returns better.

## The hurdle

The contract pays $1 if bitcoin finishes the 15-minute window at or above where it started. Bought near 50c with
the 2c taker fee and 1c of slippage, it costs about 53c, so a direction call must be right at least 53% of the
time to break even. That hit rate is the test.

## Data

Binance BTCUSDT 1-minute closes, January 2020 to November 2026. Windows start at :00, :15, :30 and :45 (UTC
minutes, as Kalshi's). Outcome proxy: up if the close of the minute ending at the window's end is at or above the
close of the minute ending at its start. Every signal uses only closes at or before the window's start.

## Signals (fixed now; "none" means no bet that window)

- T1 prior-window momentum: bet the direction of the previous 15 minutes.
- T2 prior-window reversal: bet against the previous 15 minutes.
- T3 one-hour momentum: bet the direction of the previous 60 minutes.
- T4 RSI(14) on 1-minute closes at the start: below 25, up; above 75, down; otherwise none.
- T5 Bollinger(20, 2) on 15-minute closes: below the lower band, up; above the upper band, down; otherwise none.
- T6 4-hour trend: above the 240-minute EMA with the EMA higher than 15 minutes earlier, up; below it and falling,
  down; otherwise none.
- T7 15-minute Donchian breakout: close above the highest of the prior 20 15-minute closes, up; below the lowest,
  down; otherwise none.
- T8 hour-of-day: the up rate of each UTC hour's windows in 2020-2022; bet up in hours above 52%, down in hours
  below 48%, none otherwise; scored on 2023 onward only.

## Gates (Binance history)

A signal passes if its hit rate is at least 53.5% in both 2020-2022 and 2023-2025 (T8: 2023-2025 only), with at
least 3,000 bets in each period. Also reported: hit rate by year, bets per day, and 2026 to date.

## Kalshi check (only for passing signals)

On Kalshi windows from 2026-03-01 to 2026-11-26 where the signal bets: buy that side at the last Kalshi trade
price at or before 1 minute into the window (within the prior 60 s), plus 1c, plus the taker fee; hold to
settlement. Passes if the mean return per dollar is above zero with a t-statistic of at least 2 (clustered by
day). A pass goes to a paper bot; real money only after that and the investor's approval. Bet sizing for absolute
growth (a fraction of the account per bet, from the measured hit rate) is reported for passers.
