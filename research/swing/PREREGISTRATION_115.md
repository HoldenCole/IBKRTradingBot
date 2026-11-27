# Why the 3x swing plan works, where else it works, and what could improve it: pre-registration (entry 115)

Written 2026-11-27 before any result below was computed. Nothing in parts 3 and 4 may change after results are
seen; parts 1 and 2 are descriptive.

User direction: piece out what works in the 3x swing plan (test 79), why it works, whether the technique applies
elsewhere, and what can be done to make it better.

Baseline (the live plan): SPY and QQQ; buy at the close when RSI(2) < 10 and (close below the lower Bollinger(20, 2)
band or above the 200-day average); only in Growth or Reflation months and not in the fragile state; sell at the
first close above the 5-day average or after 10 days; two slots of half the account; 3x daily-reset funds
(the entry 95 model); 9 bp a side on the fund bought; idle cash earns nothing. Sample 1999-06 to 2026-11; eras
A 1999-2006, B 2007-2016, C 2017-2026.

## Part 1. What each piece contributes (descriptive)

Remove or change one piece at a time and report CAGR, maximum drawdown and Sharpe at 3x, by era: no regime gate;
regime gate without the fragile veto; entry RSI(2) < 10 alone; RSI(2) with the Bollinger leg only; RSI(2) with the
trend leg only; exit after a fixed 3 days; SPY only; QQQ only; one slot.

## Part 2. Why it works (descriptive)

From the baseline's trades: return by holding day; overnight (close to open) against intraday (open to close)
share of the return; return by RSI(2) depth and by VIX at entry; what the gate removed (the signals in Inflation
and Deflation months and in the fragile state, and their returns); the 3x daily-reset return against three times
the 1x trade return (the path effect of daily resetting over short holds).

## Part 3. Does the technique transfer? (pre-registered)

The entry and exit rules frozen as above, one instrument at a time, one position at a time, 1x, 5 bp a side,
no regime gate (it is specific to the US book), and a second version gated by the instrument's own trend (its
month-end close above its 10-month average, known at the prior month-end). Instruments not used to build the plan:
IWM, DIA, the nine sector SPDRs, SMH, EFA, EEM, the DAX, FTSE 100 and Nikkei 225 indices, GLD, TLT, DBC and
bitcoin (Coinbase daily). Halves 1999-2012 and 2013-2026 (bitcoin 2015-2020 and 2021-2026).

An instrument "transfers" if, in either version, the mean net return per trade is above zero with a t-statistic
of at least 2 over the whole sample and is positive in both halves.

## Part 4. Candidate improvements (pre-registered)

Each changed alone from the baseline, at 3x:

- I1 add IWM (traded as a 3x Russell 2000 fund) to the universe, still two slots.
- I2 sell at the first close above the prior close instead of above the 5-day average.
- I3 2x instead of 3x on entries made when VIX is above 30.
- I4 idle cash in a T-bill ETF (T-bill yield less 0.10% a year, 9 bp a side to switch).
- I5 enter only when RSI(2) < 5 (deeper dips).

A candidate is an improvement if it raises CAGR and reduces (or does not worsen) the maximum drawdown in every one
of the three eras. Anything that improves the whole-sample result but not every era is reported as a lead only.
Adopting any change is the investor's decision.
