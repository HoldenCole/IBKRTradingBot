# When did levered funds make sense? Catching rotations, with guards against fitting the semis boom: pre-registration (entry 119)

Written 2026-11-27 before any rotation result below was computed. Nothing below may change after results are seen.

User direction: find when SOXL or any other levered fund made sense; buy-and-hold over many years is not the aim,
catching rotations is; make sure we are not overfitting to semis, the best sector of the last two years.

## Data and model

Signals on 17 dividend-adjusted 1x ETFs that each have a liquid 3x fund (entries 116-117): SPY, QQQ, IWM, XLK, SMH,
XLF, XLE, XLV, XLU, IYR, EEM, TLT, GDX, XBI, KRE, XHB, FXI. Each is held as a synthetic 3x daily-reset fund (entry
95: 3 x daily return - 2 x (T-bill + 1%) / 252 - 0.95% / 252), so the test covers 1999-2026, including the 2000-02
and 2008 crashes that today's funds mostly missed. 9 bp a side on every change in holdings; idle cash earns nothing.
A fund is eligible 12 months after its first price. Decisions at month-end closes, held for the next month.
Halves 2000-2012 and 2013-2026.

## Part 1. When did 3x make sense? (descriptive)

Monthly returns of each synthetic 3x fund, grouped by: its own trend (month-end close above its 10-month average or
not), its 6-month return rank among eligible funds (top 3 or not), its 1x realized volatility over the prior 3 months
(below 20%, 20-35%, above 35% a year), and the regime quadrant (G/R/S/D). Also the decay: the 3x month's return minus
3 x the 1x month's return, by the same volatility buckets. SMH (the SOXL proxy) is also shown on its own.

## Part 2. Rotation rules (pre-registered)

Each month-end, rank eligible funds by their trailing L-month total return; hold the top N in equal weight, but only
those whose own month-end close is above their 10-month average (the rest of the slot is cash).

- Primary rule P: L = 6, N = 2.
- Grid (all reported): L in {3, 6, 12} x N in {1, 2, 3}; judged on the grid's median, not its best.

Comparisons over the same days: the equal-weight trend rule on all eligible funds at 3x (each held while above its
10-month average, entry 117's T), SPY at 3x held while above its 10-month average, and the live swing plan.

## Guards against overfitting

1. **Without semis and tech**: rerun everything with SMH, XLK and QQQ removed from the universe.
2. **Random control**: each month pick N funds at random among those above their 10-month average (same absolute
   filter, same turnover rules), 500 draws, seed 20261127. This measures what the ranking itself adds.
3. **Both halves.**

## Pass

P passes if, in both halves: its CAGR beats the equal-weight trend rule; it beats the random control's 95th
percentile over the whole sample; and the without-semis-and-tech version of P also beats the without-semis-and-tech
trend rule in both halves. The grid median is reported beside P; if P passes but the grid median does not beat the
trend rule in both halves, P is reported as fragile.

## Today (informational, never trades)

The current month-end ranks, trends and what P would hold now are printed for information only.
