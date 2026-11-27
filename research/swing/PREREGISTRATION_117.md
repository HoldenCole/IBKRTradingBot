# The whole 3x family: mean reversion, trend following, and trend following through LEAPS: pre-registration (entry 117)

Written 2026-11-27 after downloading prices but before any strategy was run on them. Nothing below may change after
results are seen.

User direction: there are many more 3x funds than entry 116 looked at; check them all. Hypothesis from the user:
either trend following through LEAPS or mean reversion on the most volatile names is best.

## Universe

Every US-listed 3x fund found on Yahoo (76 tickers, list in `research/swing/study_3x_family.py`), daily
dividend-adjusted closes. Usable: at least 3 years of history and a median daily dollar volume of at least $1 million
over the last 6 months. One fund per underlying (SPXL dropped for UPRO, TNA for URTY, MIDU for UMDD, TTT for TMV).
Two groups: bull funds; bear funds excluding the broad US market (SPXS, SPXU, SQQQ, SDOW, SRTY, TZA, SMDD are not
tested, per the standing rule). Survivorship: only funds alive today can be downloaded. 3x funds that were closed
after collapsing are missing, which flatters buy-and-hold and trend following more than mean reversion.

All signals are on the fund's own prices. 9 bp a side. Idle cash earns nothing. Halves: 2010-2017 and 2018-2026.

## Strategies, per fund

- **M, mean reversion**: the live plan's rules (RSI(2) < 10 and (close below the lower Bollinger(20, 2) band or above
  the 200-day average); sell at the first close above the 5-day average or after 10 days); one position.
- **T, trend**: hold the fund for a month if the prior month-end close is above the average of the last 10 month-end
  closes; otherwise cash.
- **L, trend through LEAPS**: at a month-end when T is on and no calls are held, put a fixed share of the account
  (two versions: 25% and 50%) into 12-month at-the-money calls; sell at the first month-end when T is off or after 6
  months held, and buy again if T is still on. Black-Scholes, implied vol = 1.1 x the fund's 60-day realized vol with
  the entry 77 skew, risk-free from the 13-week bill; half-spread max(3% of the price, $0.05) plus $0.65 a contract each
  side; fractional contracts allowed. No historical option chains: directional answer only.

## Tests

1. **M on the family**: all bull funds' M trades pooled. Passes if the mean net return per trade is above zero with a
   t-statistic of at least 3 (clustered by entry date) and positive in both halves. Same reported for the bear group.
2. **Volatility**: funds split into thirds by realized volatility. "Mean reversion is best on the most volatile
   funds" is supported if the top third's mean M trade beats the bottom third's in both halves.
3. **T on the family**: an equal-weight portfolio of every usable bull fund, each sleeve running T, rebalanced
   monthly, against an equal-weight buy-and-hold of the same funds. Passes if T has a higher CAGR and a smaller maximum
   drawdown than buy-and-hold in both halves.
4. **L against T**: the same equal-weight portfolio with each sleeve running L. A version passes if its CAGR beats
   T's in both halves.
5. For reference, the M equal-weight portfolio and the live plan (actual UPRO/TQQQ, entry 116) over the same years.
