# Commodity Trend — Milestone 4: Vol module + full-covariance vol-targeting

**Date:** 2026-06-21
**Branch:** claude/commodity-trend-research
**Modules:** `src/commodity/loader.py`, `src/commodity/vol.py`
**Tests:** `tests/commodity/test_vol.py` (8 tests, all pass)
**Validation:** `scripts/validate_vol_module.py`

(M3 Norgate backfill skipped per user — proceeding on the Databento-only
2010-2026 panel of 10 CME commodities.)

## What was built

| Component | File | Purpose |
|---|---|---|
| `CommodityPanel` | `src/commodity/loader.py` | Source-agnostic loader; aligned multi-instrument panel with both adjusted AND raw close |
| `realized_vol` | `src/commodity/vol.py` | Per-instrument rolling annualized vol; NaN-tolerant (per-instrument min_periods) |
| `rolling_cov` | `src/commodity/vol.py` | Rolling annualized covariance matrix; pairwise NaN-handling |
| `vol_target_weights` | `src/commodity/vol.py` | Full-covariance vol-targeting with two schemes + per-instrument cap |

## Two real bugs caught + fixed during real-data validation

These would have silently corrupted every backtest if not caught here.

### Bug 1: `pct_change` on back-adjusted series

Panama-adjusted historical prices drift with cumulative roll gaps. For
contango-heavy contracts the adjusted level in 2010 differs substantially
from the raw level (gold: adj $2049 vs raw $1241, cumulative offset $-807).
For CL/HO/RB the adjusted level eventually crosses zero. Computing
`pct_change` on the adjusted series produces:
- **5,308% annualized "vol"** for RB (the one that crosses zero somewhere)
- **Systematically understated vol everywhere else** (gold showing 7% vs
  real ~20%; HG showing 12% vs real ~26%) because the same dollar move
  divided by a higher adj-level base produces a smaller percent

**Fix:** loader now carries `close` (adjusted, for SIGNALS) and `close_raw`
(unadjusted, for return DENOMINATOR). Daily return:

```
ret_t = adj.diff()[t] / raw_close.shift(1)[t]
```

This is dollar P&L per bar normalized by the actual contract notional —
the right return for a continuous-contract position. Post-fix vols are
plausible: CL 71%, NG 40%, GC 26%, HG 26%, grains 15-31%.

### Bug 2: grains drop out of joint covariance

Grains have 240 NaN returns from CBOT-vs-CME calendar mismatches. The
original `rolling_cov` required full-lookback observations per column,
causing grains to drop from every cov matrix.

**Fix:** `min_obs_frac=0.8` parameter (80% of lookback suffices). Cov uses
pandas' pairwise-NaN handling, with NaN off-diagonals zeroed (asset pair
just doesn't contribute) to keep the matrix PSD-tolerant.

## Methodology decision surfaced + resolved: weighting scheme

The spec's wording — *"each ON position sized so its contribution to
portfolio vol is target_vol / (N_on × σ_i)"* — algebraically describes
**inverse-vol weighting** (each position contributes equal vol). My
initial implementation used equal-weight-then-scale, which means CL
(σ=71%) and HG (σ=26%) get the same capital and CL dominates risk.

`vol_target_weights` now exposes `scheme={"inverse_vol", "equal_weight"}`,
defaulting to **inverse_vol** to match the spec. Both go through the same
full-covariance scaling step (target_vol / sqrt(w'Σw)) so realized vol
hits target either way. Tests verify the two schemes are distinct on
heterogeneous-vol assets.

## Real-data validation (inverse-vol, target 15%, cap 25%)

Run across the full 2010-2026 panel, all 10 instruments always ON:

| Metric | Value |
|---|---|
| Median realized portfolio vol | 15.00% |
| P95 | 15.00% |
| Min | 14.03% |
| Max | 15.00% |
| Days under target (cap-driven) | 19.0% |
| Days exceeding target | 0.0% |
| Median # capped instruments | 0 |
| Max capped any day | 5 |
| Days with any cap binding | 29.2% |
| Median gross book size | 1.16 |
| Gross P5 / P95 | 0.71 / 1.82 |

**Reads cleanly:** target hit on 81% of days; the 19% under-target days are
the cap binding on low-vol grains (corn/soybeans/wheat want >25% under
inverse-vol). Cap correctly reduces risk below target rather than
redistributing into uncapped names.

## Regime snapshots (inverse-vol)

| Regime | CL | NG | HO | RB | GC | SI | HG | ZC | ZS | ZW |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015-06-30 (calm) | 9.0 | 7.2 | 9.6 | 8.8 | 23.2 | 12.6 | 15.1 | 11.3 | 14.7 | 7.4 |
| 2020-04-30 (COVID) | 1.6 | 4.1 | 3.3 | 2.2 | 8.0 | 5.0 | 9.4 | 12.1 | 15.9 | 10.0 |
| 2022-06-30 (inflation) | 5.2 | 2.5 | 5.7 | 5.7 | 16.0 | 8.8 | 9.1 | 9.7 | 10.2 | 6.1 |

(Weights as % of NAV; all 10 instruments ON in this validation.)

Energy weights collapse in the COVID regime (1.6% for CL vs 9.0% in calm
times) because realized vol spiked — exactly the behavior vol-targeting
must produce. Low-vol assets (gold, grains) maintain larger allocations
through regimes.

## Ablation: equal-weight vs inverse-vol on 2026-06-19

| Asset | equal_weight % | inverse_vol % |
|---|---:|---:|
| CL | 8.0 | 4.6 |
| NG | 8.0 | 8.2 |
| HO | 8.0 | 5.4 |
| RB | 8.0 | 7.0 |
| GC | 8.0 | 12.5 |
| SI | 8.0 | 5.9 |
| HG | 8.0 | 12.6 |
| ZC | 8.0 | 16.0 |
| ZS | 8.0 | 21.8 |
| ZW | 8.0 | 10.6 |

Both target 15% portfolio vol. Inverse-vol concentrates in low-vol
grains/metals and underweights crude/silver — the standard CTA "risk
parity" tilt.

## Q1 methodology lock: confirmed

Full-covariance vol-targeting is essential, not nice-to-have. The
synthetic-data test `test_vol_target_correlated_assets_still_hits_target`
uses 4 assets at corr=0.8 (a crisis-like regime). Equal-weight with
independent-vol sizing would target-undershoot by ~50% in that regime;
the full-cov scaling hits 15% exactly. That's the difference between
"vol-targeted" on paper and vol-targeted in fact.

## What's NOT in this milestone

- **Returns method is per-bar simple return** suitable for vol and basic
  P&L. The portfolio backtest engine (M6) will apply position weights ×
  per-bar returns × NAV to roll equity. We're not duplicating that here.
- **No leverage cap on total book size.** The spec's only constraint is
  the per-instrument 25% cap; gross can exceed 100% (P95 = 1.82 in the
  validation). The portfolio engine in M6 will apply funding costs / T-bill
  yield on the residual when gross < 1, and document margin assumptions
  when gross > 1.
- **No instrument-specific min-trade-size constraint.** Whole-contract
  granularity is a deployment concern, not a research-backtest concern
  with $100k notional (spec). Will be addressed in M6 if we test smaller
  capital sizes.

## Where we are

| | Status |
|---|---|
| M1: Databento pull, 10 CME | ✅ |
| M2: Panama back-adjustment | ✅ |
| M3: Norgate backfill | ⏭ skipped (user direction) |
| **M4: vol module + full-cov vol-targeting** | ✅ **complete** |
| M5: 3 signal variants | next |
| M6: portfolio backtest engine + roll costs | pending |
| M7: reporting + tier classification | pending |

Next: build the three signal modules (50/200 SMA, Donchian 100/50, vol-adj
momentum 12m). Each produces a per-day ON/OFF mask per instrument that
feeds into `vol_target_weights` to size the book.
