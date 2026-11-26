# Fading big single-stock moves with price exits: pre-registration (entry 93)

Written 2026-11-26, after entry 92's results were seen and before any price-exit trade was
simulated. Nothing below may change after results are seen.

User request: exit on percentage moves, not on time. Buy or sell and close when the price has
moved a set percentage, whether that happens the same day or after a week or more.

## Carried over from entry 92 unchanged

Universe, data, filters, filing-coverage rule, development sample 2005-01-01 to 2023-12-31,
eras 2005-2014 and 2015-2023, the sealed hold-out from 2024-01-01, size L (|move| at least 5%
and at least 3 sigma versus SPY), and the news buckets E, EX, F and N. Size X is dropped.

Disclosed: entry 92 found that earnings fades lose at fixed horizons and no-filing open fades
were positive but noisy. This entry tests a different exit on the same events, so its results
are not independent of entry 92. The post-hoc "lone gap" split from entry 92 is not a trial
here and is not reported as one.

## Trades

- Entry A: the open of t, for gap events (move measured open of t versus close of t-1).
- Entry B: the close of t, for day events (move measured close of t versus close of t-1).
- Direction: fade the move. Short after a rise, long after a fall.
- Target: a fixed percentage of the entry price in the fade direction, T in {1, 2, 3, 5}%.
- Stop: a fixed percentage against the trade, S in {3, 6, 10}%.
- Time cap: exit at the close of the 20th session after entry if neither is hit.
- Daily bars only. For entry A the entry day's high and low count (both happen after the open).
  For entry B the path starts the next session. If a session opens beyond the target or stop,
  the fill is that open. If both are touched within one session, the stop is taken.
- Paths stop at 2023-12-29; a trade still open then exits at that close.

Trials: 4 buckets x 2 directions x 2 entries x 4 targets x 3 stops = 192.

## Costs

10 bp per side. Stops slip a further 10 bp. Targets fill at their price.

## Measures

Raw net return per trade (what the account earns; not market-adjusted, since an intraday target
fill has no matching SPY price), win rate, average sessions held, and net return per session held.

## Random-entry control

A fixed bracket on a drifting stock earns something by itself, and a target closer than the stop
wins often by construction. For each event, 20 random days from the same stock serve as a control:
member days with a close of at least $5, before 2024, not within 5 sessions of any of that stock's
size-L events, same entry type, direction, target, stop and cap. The event's edge is its net return
minus the average of its 20 controls.

## Gates (every one must pass on development data)

1. At least 300 events.
2. Mean net return above zero.
3. Mean net above zero in both eras.
4. t-statistic of the mean net return at least 3, clustered by event date.
5. Holm-Bonferroni across all 192 trials at a family-wise 5% level.
6. Edge over the random-entry control above zero with a clustered t of at least 2.

A trial passing every gate has its hold-out opened once (mean net above zero, one-sided p < 0.05).
Any trial failing a gate is abandoned with no re-tuning. Fading falls carries the survivorship
warning from entry 92.
