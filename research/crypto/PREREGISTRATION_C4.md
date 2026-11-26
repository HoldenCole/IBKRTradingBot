# Crypto C4: do this project's existing signals predict bitcoin? Pre-registration (entry 104)

Written 2026-11-26 before any result. Nothing below may change after results are seen.

User question: do our current signals help predict bitcoin at all? The holding period of the bitcoin trend
(entry 103) is weeks, so the practical use is a manual buy / hold / sell call.

## Data

Bitcoin: Coinbase BTC-USD daily closes, July 2015 to the last close. Equity signals: the project's own series
(S&P 500, SPY, DBC, VIX, sector ETFs) from `research/swing/data.py`. Every signal is known at the close that
starts the forward window (month-end for monthly signals, the week's last session for weekly ones). Halves:
2015-07 to 2020-12 and 2021-01 to the end.

## Signals (on = the condition holds)

Monthly, scored on bitcoin's next calendar month:

- M1 regime quadrant in force (Growth, Reflation, Inflation, Deflation), reported per quadrant; the test is
  Growth or Reflation (equity growth dial on) against the rest.
- M2 S&P 500 Quadrant Balances monthly flag INTACT (both monthly readings above zero).
- M3 S&P 500 monthly trend rising (quadrant 1 or 2).
- M4 bitcoin's monthly Quadrant Balances trend rising (quadrant 1 or 2).
- M5 bitcoin's monthly cycle rising (quadrant 1 or 2).
- M6 bitcoin above its 10-month average.

Weekly, scored on bitcoin's next week (to the next week's last S&P session):

- W1 S&P 500 weekly trend rising.
- W2 bitcoin's weekly trend rising.
- W3 bitcoin's weekly cycle rising.
- W4 VIX above 25.
- W5 the equity fragile state (S&P 0-3% above its 200-day average with 20-day volatility above 16%).

Reference: D1, the entry-103 bitcoin daily trend (on or off), scored on the next 5 days.

## Measures and verdict for each signal

Mean forward return of bitcoin when on and when off; the difference; its Welch t-statistic; the same in each
half. A signal "helps" if the difference has the same sign in both halves and |t| is at least 2 over the
whole sample. With about 135 months and 590 weeks, this can only find a strong effect.

## Does anything improve the bitcoin trend?

Long bitcoin at 1x and at 2x (funding not modelled; this is a spot-price comparison) when the entry-103
daily trend is on, and:

- F1: also requires the S&P 500 above its 10-month average (the regime growth dial).
- F2: also requires the S&P 500 monthly flag not BROKEN.
- F3: also requires bitcoin's weekly trend rising (W2).

A filter improves the trend only if it raises CAGR and reduces maximum drawdown in both halves, at 1x.

## Reported

Today's reading of every signal, for the manual call.
