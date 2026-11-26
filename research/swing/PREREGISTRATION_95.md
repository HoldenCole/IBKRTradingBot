# Bollinger bands on the indices, played through 3x funds: pre-registration (entry 95)

Written 2026-11-26 before any result. Nothing below may change after results are seen.

User request: trade Bollinger bands on the actual indices over different time frames, and play
the view through the levered ETFs. Standing rules: never short the broad US market, so every
rule is long or flat; the small account is always levered, 3x by default.

Earlier evidence, disclosed: daily lower-band dip-buys on ETFs were positive (test 75), daily
upper-band breakouts were not (75b), weekly bands were unstable (76), tight stops broke the
bounce at every bar size (80), and the close below the lower band was the best buy trigger (83).
New here: signals on the index itself, monthly bands, time-frame combinations, a 3x account, and
history back to 1988.

## Data

- Signals: closes of the S&P 500 (^GSPC) and Nasdaq-100 (^NDX) from Yahoo.
- Weekly bars end on the last session of each week; monthly bars on the last session of the month.
- Fund returns: index total return times 3, less 2 x (T-bill + 1%) financing and 0.95% expense a
  year, charged daily while invested (the model of tests 79 and 89). Total return is SPY's
  adjusted close from 1993 (QQQ's from 1999), and before that the index plus a dividend yield of
  3.0% a year (S&P 500) or 0.5% (Nasdaq-100). The model is checked against UPRO and TQQQ from
  their launch.
- Idle cash earns nothing: IBKR pays no interest on the first $10,000.
- Costs: 9 bp per side (test 89's $1,000-account cost).
- Execution: at the close of the bar that gives the signal (a market-on-close order using the
  price shortly before the close). Sensitivity: execution one session later.

## Eras

1988-2006 and 2007-2026 (to 2026-11-25). Bands need 20 bars, so the monthly bands are warm by 1988.

## Rules (Bollinger 20 bars, 2 standard deviations, on each time frame D, W, M)

1. Dip to middle: buy on a close below the lower band; sell on a close at or above the middle band.
2. Dip to upper: buy on a close below the lower band; sell on a close at or above the upper band.
3. Breakout: buy on a close above the upper band; sell on a close below the middle band.
4. Above middle: hold while the close is above the middle band; flat below it.
5. Daily dip to middle, taken only while the last completed weekly close is above the weekly middle band.
6. Daily dip to middle, taken only while the last completed monthly close is above the monthly middle band.

That is 4 rules x 3 time frames + 2 combinations = 14 rules per index, 28 trials. No stops (test 80).

## Benchmarks

- 3x buy and hold of the same index (same model and costs).
- 1x buy and hold.
- The test-79 swing account at 3x (1999-2026), the live plan.

## Gates

A rule passes if, in BOTH eras, it beats 3x buy and hold of its index on CAGR, Sharpe and maximum
drawdown (the two-era rule: every metric better in both eras). A passer must also pass with each of
the four neighbours n in {10, 30} at k = 2, and k in {1.5, 2.5} at n = 20.

A passer is a candidate to add to or replace the live plan only if, over 1999-2026, it beats the
test-79 3x account on CAGR and on maximum drawdown, or its daily returns correlate with that account
below 0.5 (a diversifier). That is reported; adopting anything is the investor's decision.
