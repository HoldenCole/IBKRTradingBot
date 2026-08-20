# Commodity Trend Research — Results

Executes the locked spec in `New Trading Strats` (three trend variants, 13-commodity basket, vol-targeted sizing, pre-registered Tier A-D criteria). Completed 2026-08-20. Full daily return series: `research/commodity_trend_series.csv`.

## Data (availability check per spec)

- 12 of 13 instruments from 2000 (KC/SB from early 2000); **BZ from 2007-07** as the spec anticipated — documented, contributes from 2007. Coverage 96% of business days.
- **Material data limitation:** Yahoo continuous futures are front-month splices with no back-adjustment — their return path is spot-like and omits roll yield (diagnostic: NG=F shows 0.58x since 2000 while a real long NG futures position lost far more to contango). Mitigation: carry drag calibrated against futures-holding ETFs with real roll costs — **CL 8.9%/yr (vs USO), NG 24.3%/yr (vs UNG)** — applied to ON-days: energy fully, grains/softs at half CL's, metals at financing-only. Both raw and adjusted results reported; verdicts use adjusted. Spec's per-roll bid-ask costs and 5bps trade costs included.

## Results (2000-2026, T-bills on idle capital, 15% vol target, 25% position cap)

| Variant | CAGR | Sortino | maxDD | Sub-Sortino 00-09 / 10-17 / 18-26 | Avg positions |
|---|---|---|---|---|---|
| V1 SMA 50/200 (adj) | −0.5% | −0.28 | −60% | 0.09 / −0.72 / −0.34 | 2.6 |
| V2 Donchian 100/50 (adj) | +2.0% | 0.06 | −50% | 0.51 / −0.50 / 0.07 | 4.7 |
| V3 vol-adj momentum (adj) | +1.8% | 0.02 | −43% | 0.06 / −0.46 / 0.41 | 3.2 |
| Equal-weight buy & hold (adj) | +1.5% | 0.11 | −82% | — | 13 |

Raw (carry-bias-inflated) numbers are better but still fail: best is V2 raw at Sortino 0.42 — under the Tier C floor of 0.7.

## Verdict per the locked criteria: ALL THREE VARIANTS ARE TIER D — ELIMINATED

The spec's own interpretation applies: *"If all three fail → commodity trend doesn't work in our sample as we've specified it."* The margin to even Tier C is wide enough that no plausible error in the carry adjustment changes the verdict. The 2010-2017 sub-period is the killer for every variant — consistent with the real-world CTA "trend winter" of that decade, which is corroborating evidence that the backtest is measuring reality.

## What DID show up (interpretable findings, per spec)

1. **The diversification property is real even though the returns are not.** Correlation with the indices strategy: 0.08-0.10 across all variants. Bear-regime behavior: 2008 +8/+8/+2%, and V3 made **+13% in 2022** — crisis alpha appeared exactly where the managed-futures literature predicts.
2. **Long/flat is not how CTAs earned their track record.** The spec's variants are long-or-cash. Real trend programs are long/SHORT — 2022's +25-40% CTA returns came substantially from short bonds/short equities/long energy simultaneously. A long-short variant is a *different, future spec* (this is an observation, not a tuned re-run).
3. Signal choice mattered less than expected: cross-variant correlations 0.56-0.71, all failing together.

## Portfolio implication

No commodity-trend sleeve enters the quadrant matrix. The rotation's existing commodity exposure (DBC/XLE held only in inflationary quadrants) already captures the conditional benefit with none of this complexity, and the quadrant switch itself is doing the trend-timing at the regime level.
