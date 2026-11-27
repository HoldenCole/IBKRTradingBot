# Selling Kalshi hourly bitcoin contracts before settlement: pre-registration (entry 113)

Written 2026-11-27 before any hourly early-exit result was computed. Nothing below may change after results are
seen.

User direction: try the hourly contracts with profit targets.

## Entries (unchanged from entry 111)

The three hourly signals (H1 fade hourly Bollinger, H2 fade 15-minute Bollinger for the next hour, H3 fade hourly
RSI) with their actual Kalshi entries: the strike nearest the basis-adjusted Binance price, bought at the last
trade within 120 seconds before 2 minutes into the hour, plus 1c, plus the taker fee; March to November 2026.

## The contract's value during the hour

At each minute m = 3 to 59 after the hour opens: fair value of YES ("above the strike at the hour's end") =
N( ln(S / K) / (sigma x sqrt(tau)) ), with S the Binance 1-minute close times (1 + basis), the basis being the
median of the previous 96 settled 15-minute windows' measured basis (entry 109) at the time of the entry, K the
strike, sigma the last 60 minutes' 1-minute volatility, and tau = 60 - m - 0.5 minutes. The held side's sale
price = its fair value minus 1c, minus the taker fee on the sale.

## Exit rules (6 per signal, 18 trials)

Profit target X cents above the entry price of the held side, X in {5, 10, 15}; no stop, or a stop 10 cents below
the entry price. First minute either is reached, sell; otherwise hold to settlement. Hold-to-settlement reported
for comparison.

## Check and gate

A random 300 early exits (seed 20261127) are checked against the last actual Kalshi trade at or before the exit
minute; if actual is worse than modelled by more than 0.5c on average, all early sales are reduced by that amount.
A trial passes if its mean return per dollar is above zero with a t-statistic of at least 3 (clustered by day)
and it is positive in September-November 2026.
