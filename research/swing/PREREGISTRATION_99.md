# Trailing stops on the monthly Quadrant Balances bets: pre-registration (entry 99)

Written 2026-11-26 before any result. Nothing below may change after results are seen.

User direction: entry 98's monthly bets are the most promising so far; add a trailing stop to
prevent declines larger than 25%.

Disclosed: designed after seeing entry 98, on the same data, so a pass here is weaker evidence
than a fresh test. The stop levels and re-entry rules below are fixed now.

## Base designs (entry 98, all in at 3x, idle cash earns nothing, 9 bp a side)

- A: monthly trend turns up below zero, hold until the monthly trend crosses below zero.
- B: monthly cycle crosses back above zero, hold until the monthly trend crosses below zero.
- C: monthly trend turns up below zero, hold 12 months.

## Stop

Trailing stop on the 3x position: exit when the position's value closes X% or more below its
highest close since entry. X in {15, 20, 25, 30}%. Exit at that close (a stop can lose more than X
when one day's move is large).

## Re-entry after a stop, inside the base design's holding window

- R1: none. Wait for the next fresh buy signal of the base design.
- R2: re-enter at the first month-end close at which the S&P 500 is above its 10-month average,
  if the base design's window is still open (A, B: the monthly sell has not fired; C: the 12 months
  have not ended). The stop resets at each re-entry.

24 trials: 3 designs x 4 stops x 2 re-entry rules.

## Data and eras

As entry 98: S&P 500 from 1950, 3x model, eras 1950-1986, 1987-2006, 2007-2026.

Sensitivity (reported, not gated), 1984 on, where daily highs and lows exist: the stop as a real
intraday trailing-stop order. The fund's intraday low is modelled as the prior close times
(1 + 3 x (index low / prior index close - 1)). The order fills at the stop price, or at the
modelled open if the fund opens below the stop.

## Measures

CAGR, maximum drawdown of the account, the worst single day, the number of stops, the share of days
the account is more than 25% below its peak, and the 3-year multiple spread.

## Gates

A trial passes if, in each of the three eras, it beats 3x buy and hold on CAGR and on maximum
drawdown, and beats its own no-stop base design on maximum drawdown. Reported alongside: whether
its maximum drawdown is within the user's 25% limit. Adopting anything is the investor's decision.
