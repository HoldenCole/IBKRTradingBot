# Few, large, all-in bets in a 3x S&P 500 fund: pre-registration (entry 98)

Written 2026-11-26 before any result. Nothing below may change after results are seen.

User direction: about 10% a year is not the purpose of the small account. It wants a small number
of high-risk trades with large exposure. So every design here puts the WHOLE account into a 3x
S&P 500 fund on a rare signal, and holds cash (earning nothing) otherwise.

## Data

- S&P 500 daily closes from 1950 (the Quadrant Balances history). Total return: SPY's adjusted
  close from 1993-02; before that the index plus a dividend yield of 4.0% a year (1950-1986) or
  3.2% (1987-1993). T-bills: FRED TB3MS monthly before 1984, ^IRX daily after.
- 3x fund: 3 x daily total return, less 2 x (T-bill + 1%) and 0.95% a year (entries 95-97; checked
  against UPRO at a daily correlation of 0.998). 3x funds did not exist before 2009, so earlier
  results are hypothetical.
- Costs: 9 bp per side on the whole account.
- Eras: 1950-1986, 1987-2006, 2007-2026 (to the last close).

## Designs (all at 3x, 100% of the account per trade)

Quadrant Balances signals, as defined in entry 87, computed on month-end and week-end closes:

1. M-trend-up, 12 months: buy at the month-end close when the monthly trend turns up below zero; sell 12 month-ends later.
2. M-trend-up, until sell: the same buy; sell at the month-end close when the monthly trend crosses below zero.
3. M-cycle-confirm, 12 months: buy when the monthly cycle crosses back above zero; sell 12 month-ends later.
4. M-cycle-confirm, until sell: the same buy; sell when the monthly trend crosses below zero.
5. W-mature-turn, 13 weeks: buy at the week-end close when the weekly cycle turns up while the weekly trend
   decline is in week 4 or later and the last completed month is intact (both monthly readings above zero);
   sell 13 week-ends later.

Daily signals:

6. Deep dip: buy at the close when the S&P 500 closes at least 1% below its lower Bollinger band (20, 2);
   sell at the first close above its 5-day average or after 10 sessions.
7. Swing plan, one slot: test 79's signals with the whole account in one position (1999 on).
8. Swing plan, two slots: the live design, for reference (1999 on).

A signal that fires while the account is already invested is ignored.

## References

3x buy and hold, 1x buy and hold.

## Measures

CAGR, maximum drawdown, trades a year, share of time invested, mean and worst trade, and the spread of
3-year outcomes (the account multiple over every 3-year window: 10th percentile, median, 90th
percentile, and the share of windows that end below half the starting balance).

## Gates

A design passes if it beats 3x buy and hold on CAGR and on maximum drawdown in each era it covers
(designs 1-6: all three eras; designs 7-8: 1999-2006 and 2007-2026). Adopting anything is the
investor's decision.
