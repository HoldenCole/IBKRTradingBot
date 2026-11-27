# Selling Kalshi bitcoin contracts before settlement: profit targets and stops: pre-registration (entry 112)

Written 2026-11-27 before any early-exit result was computed. Nothing below may change after results are seen.

User point: entries 110-111 held every contract to settlement. A contract can be sold at its current price
at any time, like an option, so profit targets (and stops) can be used: it only has to move in the right
direction.

## Entries (unchanged from entries 110-111)

The six 15-minute signals that passed the Binance gate, with their actual Kalshi entry prices (last trade within
60 seconds before 1 minute into the window, plus 1c, plus the taker fee), March to November 2026: T5 Bollinger
fade, B1 breakout fade, C1 stretched-move fade, C2 stochastic fade, C3 runs-of-three fade, C5 Bollinger-and-RSI.

## The contract's value during the window

At each minute m = 2 to 14 after the open, the fair value of the held side is computed as in entry 109 (Binance
1-minute close times (1 + measured basis), the window's strike, the last 60 minutes' volatility, minutes left),
which matched Kalshi's prices to within 1-2 cents in every probability bucket. The sale price = fair value of
the held side minus 1 cent (half the spread), minus the taker fee on that sale price.

## Exit rules (6 per signal, 36 trials)

Profit target X cents above the entry price (the side's price before fee): X in {5, 10, 15}; with no stop, or
with a stop at 10 cents below the entry price. The first minute that the target or the stop is reached, the
contract is sold at that minute's sale price. Otherwise it is held to settlement. Hold-to-settlement (entries
110-111) is reported for comparison.

## Check of the modelled sale prices

For a random 400 of the early exits (seed 20261127), the last actual Kalshi trade at or before the exit minute
is fetched. The mean of (actual price - modelled fair value) for the held side is reported. If it is below
-0.5 cents (actual worse than modelled), every early-exit sale is reduced by that amount and the results are
recomputed.

## Gate

With 36 trials: a trial passes if its mean return per dollar is above zero with a t-statistic of at least 3
(clustered by day), and it is positive in September-November 2026. A pass goes to a paper bot; real money only
after that and the investor's approval.
