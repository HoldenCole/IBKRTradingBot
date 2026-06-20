# Commodity Trend — Milestone 1: Databento data acquisition

**Date:** 2026-06-20
**Branch:** claude/commodity-trend-research
**Scripts:** `src/data/databento_loader.py`, `scripts/pull_commodity_data.py`

First step of the Hybrid data plan: the 10 CME commodities from Databento
(2010-2026). Norgate backfill (2000-2009 + ICE trio BRN/SB/KC) is the
separate next data step.

## Outcome: clean daily series for all 10 CME commodities

| Root | Label | Bars | b/yr | First | Last | LastClose | Hygiene |
|---|---|---:|---:|---|---|---:|---|
| CL | WTI crude | 4158 | 259 | 2010-06-07 | 2026-06-19 | 76.54 | OK |
| NG | Natural gas | 4158 | 259 | 2010-06-07 | 2026-06-19 | 3.20 | OK |
| HO | Heating oil | 4158 | 259 | 2010-06-07 | 2026-06-19 | 3.15 | OK |
| RB | RBOB gasoline | 4158 | 259 | 2010-06-07 | 2026-06-19 | 2.91 | OK |
| GC | Gold | 4157 | 259 | 2010-06-07 | 2026-06-19 | 4172.90 | OK |
| SI | Silver | 4157 | 259 | 2010-06-07 | 2026-06-19 | 64.91 | OK |
| HG | Copper | 4157 | 259 | 2010-06-07 | 2026-06-19 | 6.34 | OK |
| ZC | Corn | 4042 | 252 | 2010-06-07 | 2026-06-18 | 417.50 | OK |
| ZS | Soybeans | 4042 | 252 | 2010-06-07 | 2026-06-18 | 1142.00 | OK |
| ZW | Wheat | 4042 | 252 | 2010-06-07 | 2026-06-18 | 613.25 | OK |

All instruments: zero NaN/zero/negative closes, monotonic dates, zero
residual Sunday bars. Energy/metals 259 bars/yr; grains 252/yr (CBOT ags
have no Sunday electronic session).

## Two data-quality issues found and fixed

### 1. Streaming connection drops on long ranges
Databento's `timeseries.get_range` streams, and the connection drops from
this environment on ranges beyond ~6 months (`Error streaming response`).
**Fix:** chunk into 6-month windows with 3x retries, concatenate + dedupe
(`_six_month_windows` + `_fetch_chunk`). ~5s per chunk.

### 2. CME Sunday-evening sessions mis-bucketed
`ohlcv-1d` buckets by UTC calendar day, so the CME Sunday-evening session
(part of Monday's CME trade date) appeared as a separate tiny-volume Sunday
bar — inflating the calendar to ~310 bars/yr and creating partial-session
bars that would distort signals + vol. Example: 2024-01-07 (Sun) vol 2,995
vs Monday's 268,770.
**Fix:** `collapse_to_trade_date()` reassigns Sunday bars to Monday and
aggregates OHLCV (first/max/min/last/sum). Raw cache stays faithful to
source; collapse applied explicitly on load.

### 3. Roll-rule change: calendar -> volume
Initial calendar-roll (`.c.0`) landed on illiquid metal contract months
(silver concentrates in Mar/May/Jul/Sep/Dec) that don't trade daily,
producing no-trade gaps: **silver had 118 gaps >4 days, only 184-247
bars/yr** (lost ~30% of sessions); gold milder (13 gaps). Energy/grains
were fine.
**Fix:** switched default to volume-roll (`.v.0`) — follows the most-liquid
contract (trades every session) and is the standard CTA trend-research
convention. Verified 2015: SI 210->310, GC ->310, CL/ZC unchanged.

**Side benefit:** volume roll sidesteps the CL April-2020 negative-price
blowup. Volume had already rolled off the expiring May contract (which went
to -$2.67 and produced a -439% artifact under calendar roll) to June, which
stayed positive. CL April-2020 min close is now +$12.26, and the negative-
close hygiene flag is gone. (The Panama back-adjustment in milestone 2 must
still handle sign-change robustness in case any series touches it.)

## Methodology decisions locked here

- **Roll rule:** volume-based (`.v.0` / `.v.1`), all instruments.
- **Bar definition:** one bar per CME trade date (Sunday collapsed into Monday).
- **Close convention:** Databento `ohlcv-1d` close is the last electronic
  print before the UTC-day boundary (~6-7pm CT), not the 2:30pm CT
  settlement. Consistent across the series, fine for daily trend signals;
  the Norgate backfill (official settlements) provides a cross-check.

## Remaining large moves are expected (not bugs)

The unadjusted continuous still contains roll gaps — e.g. CL -34%, NG -31%
single-day moves, NG 4.7% of days >7%. These are removed by Panama
difference back-adjustment (milestone 2), which uses the second-month
(`.v.1`) series to isolate each roll gap.

## Next: Milestone 2 — Panama back-adjustment
- Pull `.v.1` (second month by volume) for all 10
- Detect roll dates (instrument_id change in `.v.0`)
- Compute roll gap = `.v.1`[t-1] - `.v.0`[t-1] at each roll
- Apply cumulative difference adjustment back through history
- Cross-check against Norgate's own back-adjusted series once backfill lands

## Data location (gitignored — licensed)
`data/commodities/databento_raw/<SYM>_v_0__2010-06-06__2026-06-20.csv`
