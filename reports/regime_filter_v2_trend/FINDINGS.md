# Trend filter (Filter 1) — NOT USEFUL per locked decision criteria

**Date:** 2026-05-02
**Filter:** ON when QQQ close > SMA(50) AND SMA(50) > SMA(200); OFF otherwise.
**Method:** engine-level gating (filter blocks signals at queue time). Trade-
level gating ("just drop trades") under-counts the filter because
`max_concurrent=1` would let blocked trades free up capacity for next
signals — engine-level gating handles correctly.

## Result tables

### Full period 2018-01-01 → 2026-04-15

| Metric | Unfilt | Filtered | Lift | BAH-full | **BAH-ON-only** |
|---|---|---|---|---|---|
| Sortino | 0.59 | **0.15** | **−0.43** | 1.08 | **2.65** |
| Sharpe | 0.67 | 0.31 | −0.36 | 0.83 | 2.51 |
| Total return | +83.4% | +17.5% | −65.9 pp | +302.2% | **+1150.0%** |
| Max drawdown | −15.5% | −15.3% | +0.2 pp | −35.6% | −10.8% |
| Trades | 337 | 171 | −166 | — | — |
| Trade drop | — | — | **49.3%** | — | — |
| Filter ON-days | — | — | — | — | 1231/2082 (59%) |

### Train 2018-2022

| Metric | Unfilt | Filtered | Lift | BAH-full | BAH-ON-only |
|---|---|---|---|---|---|
| Sortino | 0.72 | **0.09** | **−0.64** | 0.68 | 2.21 |
| Sharpe | 0.83 | 0.20 | −0.64 | 0.53 | 2.26 |
| Return | +66.4% | +6.0% | −60.4 pp | +68.0% | +297.5% |
| Max DD | −15.5% | −15.3% | +0.2 pp | −35.6% | −10.8% |
| Trades | 213 | 98 | −115 | — | — |
| Drop | — | — | 54.0% | — | — |

### Test 2023-2026

| Metric | Unfilt | Filtered | Lift | BAH-full | BAH-ON-only |
|---|---|---|---|---|---|
| Sortino | 0.30 | 0.32 | **+0.02** | 2.07 | 3.46 |
| Sharpe | 0.32 | 0.52 | +0.20 | 1.46 | 2.89 |
| Return | +9.2% | +11.0% | +1.7 pp | +141.0% | +214.5% |
| Max DD | −10.5% | −8.5% | +2.0 pp | −22.9% | −5.5% |
| Trades | 124 | 73 | −51 | — | — |
| Drop | — | — | 41.1% | — | — |

## Per-regime drop (full period)

| Regime | N_total | N_kept | N_drop | Drop_pnl | Kept_pnl |
|---|---|---|---|---|---|
| bull (4 yrs) | 157 | 95 | 62 | **−$1,188** | +$2,917 |
| crisis_recovery (2020) | 50 | 33 | 17 | +$1,654 | +$1,114 |
| **bear (2022)** | **49** | **0** | **49** | **+$2,741** | **$0** |
| chop_to_correction (2018) | 40 | 24 | 16 | −$260 | −$618 |
| bull_chop (2025) | 33 | 14 | 19 | +$1,002 | +$96 |
| mixed (2026) | 8 | 2 | 6 | −$326 | −$459 |

## Decision rule application

| Criterion | Required | Actual | Pass |
|---|---|---|---|
| 1. Sortino lift positive in BOTH train and test | both > 0 | train: −0.64, test: +0.02 | **FAIL** |
| 2. Filtered Sortino > BAH-on-ON-days Sortino (full) | filtered > BAH-ON-only | 0.15 vs 2.65 | **FAIL** |
| 3. Trade drop < 50% | < 50% | 49.3% | PASS |

**Verdict: NOT USEFUL.** Two of three criteria fail.

## Why this filter fails — the per-regime breakdown explains it

The filter's design is asymmetric (ON only in confirmed bullish trends).
Applied to a long+short strategy, it has three failure modes:

1. **Bear regime entirely blocked.** All 49 bear-regime trades dropped,
   forfeiting **+$2,741** of profit from IBS-shorts that fired during
   2022's downtrend. The filter mechanically excludes the entire
   regime where shorts work. This is the single largest cost.

2. **Bull-regime trades partially blocked, removing winners.** 62 of
   157 bull-regime trades dropped, with the dropped set having
   −$1,188 P&L on average — meaning the filter is dropping trades
   that overall LOST money in bull regimes, but the kept bull-regime
   trades (+$2,917) had the same per-trade profile as the
   unfiltered bull-regime trades. Net effect: filter is removing
   noise in bulls but the lift is small.

3. **Filtered Sortino dramatically below BAH-ON-only.** The "what if I
   just held QQQ during bullish trends" benchmark is Sortino 2.65 in
   full period. The filtered IBS-LS strategy is 0.15. **Buy-and-hold
   on filter-ON days is nearly 18× better at risk-adjusted return
   than running IBS-LS during the same days.** This is the structural
   finding — IBS-LS is dominated by BAH even when the bullish-trend
   selection is applied identically to both.

## What this rules out

Per validation discipline: **do NOT tune MA windows.** Tested rule was
the user's spec: SMA(50) and SMA(200). Adjusting to SMA(20)/(100) or
similar would be data-fitting on a sample where the underlying
hypothesis already failed.

The verdict is: **trend-only filtering does not capture IBS-LS's
failure regimes**. Within each regime (including bull), there's no
way to use trend-coherence alone to separate the IBS-LS trades that
make money from the ones that lose. The signal lives in something
else — likely intraday behavior, IV / vol-of-vol, breadth, or
something the trend MAs cannot see.

## What this means for the regime model

The user's separate regime model is the real test. It can use richer
features (vol structure, correlations, breadth, options flow) that
this simple trend filter cannot access. The negative result here
doesn't disprove regime-filtering as an approach — it disproves
**simple-trend-only** filtering for IBS-LS specifically.

The data did show one structural fact decisively: **BAH-on-trend-ON
days produced Sortino 2.65 / +1150% return over 8 years.** This is
extraordinary and is itself a candidate strategy: just hold QQQ when
SMA(50) > SMA(200) AND price > SMA(50), cash otherwise. Worth scoping
as its own strategy candidate independent of IBS — in fact, this
might be the buy-and-hold-lift component the portfolio thesis needs.

## Status

- BullishTrendFilter as IBS-LS gate: **dropped per locked criteria**.
- BAH-on-trend-ON-days as a standalone strategy candidate: **NEW
  candidate to scope** (not run yet — scoping note only).
- Regime filter approach itself: **still alive, awaiting user's
  separate model**. This filter's failure narrows the requirement:
  whatever the model uses, simple trend MAs aren't enough.

## Files

- `src/backtest/regime_filter.py` — `BullishTrendFilter` class added
- `scripts/run_trend_filter.py` — reproducible runner
- `reports/regime_filter_v2_trend/raw_output.txt` — full output
