# Intraday forex technical rules: pre-registration

Written 2026-11-26, committed before any backtest in this folder was run. Nothing below may be
changed after results are seen. Any later idea is a new entry with its own date, and every
variant ever run is counted in `trials.csv`.

Source of the plan: `reports/Intraday forex TA tools and repos.md`, section "A staged plan that
expects a null result". The expected outcome is that every idea fails.

## Data

- FXCM public minute candles, bid and ask separately, UTC, 2012-01-02 to 2026 week 46.
  Dukascopy (the report's first choice) closed its free feed on or before 2026-11-26.
- Development sample: 2012-01-01 to 2024-11-30.
- Hold-out: 2024-12-01 to the end of the data. The loader refuses it without a token. A token is
  issued once per rule, only for a rule that has passed every development gate, and the
  opening is logged in `holdout_log.csv`. A rule whose hold-out has been opened cannot be
  re-opened, re-tuned or re-tested on the hold-out.
- Two independent development windows: 2012-01-01 to 2017-12-31 and 2018-01-01 to 2024-11-30.

## Costs

- Every fill crosses an effective spread: `max(feed spread at the bar open, base spread) x stress`.
  Buys pay mid + half of it, sells receive mid - half.
- Base spread, in pips (OANDA US spread-only account, from the report): EUR/USD 1.4, GBP/USD 2.0,
  USD/JPY 1.4. EUR/GBP 2.0 and AUD/NZD 3.0 are assumptions (no primary source found).
- Stop orders slip a further 0.2 pips x stress, and fill at the bar open if price gapped through.
  Limit (target) orders fill at their price, no slippage.
- If a stop and a target are both touched inside one minute, the stop is taken.
- Stress levels: 1.0 (base), 1.5, 2.0. A CME Micro EUR/USD taker round trip (about 1.4 bp, about
  1.6 pips) sits between 1.0 and 1.5 and is reported for reference.
- No position is held through 17:00 New York, so there is no financing.
- No entries from 24 December to 2 January.
- No entry when the feed spread at the entry bar exceeds 2.5 times the base spread.

## Ideas and every variant (20 trials on EUR/USD)

All entries are at the open of the first minute bar at or after the signal time. Signals use
only bars that have closed.

### 1. Session drift (3 trials, no free parameters)

From Krohn, Mueller and Whelan (2024): the dollar strengthens into the European fixes and
weakens after the London fix.

- `drift_A`: short EUR/USD at 08:00 Europe/Berlin, cover at 14:15 Europe/Berlin (ECB fix).
- `drift_B`: long EUR/USD at 16:00 Europe/London (WM fix), exit at 16:45 America/New_York.
- `drift_AB`: both legs on every eligible day.
- Catastrophe stop 1.0% from entry. Monday to Friday.

### 2. Hourly mean reversion (8 trials)

One-hour mid bars on clock hours (UTC). z = (close - SMA20) / SD20 (population SD).
ATR14 = 14-bar mean of the hourly true range.

- Long when z < -k, short when z > +k, on the close of an hourly bar.
- Target: the SMA20 at the signal bar. Stop: entry mid -/+ m x ATR14. Time stop: T hours.
- Forced flat at the next 16:45 New York after entry.
- No entry between 15:00 and 19:00 New York, and none after 12:00 New York on Friday.
- One position at a time; signals while in a position are skipped.
- Grid: k in {2.0, 2.5} x m in {1.0, 2.0} x T in {4, 8}. Trial ids `mr_k{k}_m{m}_T{T}`.

### 3. Round-number conditioning (8 trials)

The same 8 mean-reversion variants, taking a long fade only when a level ending in 00 or 50
(EUR/USD 0.0050 grid) lies 0 to 10 pips below the entry price, and a short fade only when one
lies 0 to 10 pips above. Trial ids `rn_k{k}_m{m}_T{T}`.

Controls (not counted as trials, they are null comparisons): the same filter on grids shifted by
13, 27 and 37 pips. The round-number effect is supported only if the true grid beats all three.

### 4. London breakout of the Asian range (1 trial, a calibration test)

- Range: mid high and low from 00:00 to 07:00 Europe/London.
- From 07:00 to 12:00 London: buy stop at range high + 1 pip, sell stop at range low - 1 pip.
  The first triggered wins; if both trigger in the same minute the day is skipped.
- Stop at the opposite edge of the range, target one range width beyond entry, exit by 16:45 New York.
- Skip days with a range under 3 pips or over 100 pips.
- Expected result: weak or negative. A strongly positive result is treated first as a bug or a leak.

## Measures

Per trade: net return in basis points of notional, cost in basis points, and for ideas 2 to 4 the
return in R (net return divided by the entry-to-stop distance).
Break-even cost = mean gross return per trade. Cost ratio = break-even cost / mean base cost.

## Gates (every one must pass on development data, at base cost)

1. At least 1,000 trades in the development sample; otherwise the result is "insufficient", not a pass.
2. Mean net return per trade above zero.
3. Cost ratio at least 2.
4. Mean net above zero in both development windows.
5. Snooping: Hansen's SPA test across all 20 trials (daily net P&L, benchmark zero) with p < 0.05
   for the family's best trial, and that trial's own t-statistic at least 3.
6. Beats a random-entry null: 200 simulations with the same number of trades, same direction mix,
   same stop and target distances and same holding limits, entries at random eligible minutes.
   One-sided p < 0.05 on mean net return.
7. For mean reversion only: a walk-forward test (select the best of the 8 variants on a rolling
   3-year window with at least 100 trades, trade the next 3 months) must have positive mean net
   return over its stitched out-of-sample record.
8. For round numbers only: the true grid must beat all three shifted control grids.

A rule passing every gate has its hold-out opened once. It passes the hold-out if mean net return
per trade is above zero with a one-sided p < 0.05. Only then does it go on to a second pair
(GBP/USD for the drift; EUR/GBP and AUD/NZD for mean reversion), paper trading and the staged
plan in the report.

Any idea failing a development gate is abandoned with no re-tuning.

## Statistical power, stated in advance

At one or two trades a day the development sample gives roughly 3,000 to 6,000 trades. That is
enough to detect a net edge of about 0.10R at t = 3, not one of 0.04R.
