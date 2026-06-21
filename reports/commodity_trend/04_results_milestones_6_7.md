# Commodity Trend Research — Results & Decision (Milestones 6 + 7)

**Date:** 2026-06-21
**Branch:** claude/commodity-trend-research
**Engine:** `src/commodity/engine.py` · **Runner:** `scripts/run_commodity_backtest.py`
**Raw output:** `RESULTS_raw_output.txt`

## Scope of this round (read first)

- **Universe:** 10 CME commodities (CL, NG, HO, RB, GC, SI, HG, ZC, ZS, ZW).
- **Period:** 2010-06 → 2026-06 (Databento). **Missing vs the full spec:**
  Brent/Sugar/Coffee (3 ICE instruments) and the **2000-2009 sub-period**,
  both pending the deferred Norgate backfill (M3).
- **This matters for the verdict.** 2010-2026 is a notoriously *hostile*
  window for commodity trend — a secular commodity bear (2011-2020) with
  repeated whipsaws. The single best historical environment for commodity
  trend-following (the 2003-2008 supercycle and the 2008 crash, a textbook
  CTA win) is in the missing 2000-2009 block. **Treat these results as
  provisional / a lower bound, not the final word.**
- Sizing: full-covariance vol-targeting (inverse-vol), target 15%, 25% cap.
  Net of per-sector roll + bid-ask costs. T-bill 2%/yr on idle capital.
  No same-bar look-ahead (signal at t-1 → return at t).

## Headline metrics (full sample, net of costs)

| Variant | CAGR | Sharpe | Sortino | MaxDD | Vol | AT-CAGR | Tier |
|---|---:|---:|---:|---:|---:|---:|---|
| **EW commodity BAH** (benchmark) | +2.6% | 0.24 | 0.33 | 70% | 17% | +2.0% | — |
| V1 — Classic 50/200 SMA | +1.2% | 0.16 | 0.22 | 44% | 11% | +0.9% | **D** |
| V2 — Donchian 100/50 | −2.6% | −0.14 | −0.19 | 59% | 13% | −2.6% | **D** |
| V3 — Vol-adjusted 12m momentum | **+5.3%** | **0.49** | **0.71** | **38%** | 12% | **+4.2%** | **C** |

(After-tax = Section 1256 60/40, higher bracket.)

## What the triangulation says

The spec designed the three variants to triangulate *where* trend edge
lives in commodities. The result:

> **V3 (vol-adjusted momentum) >> V1 (SMA) > V2 (Donchian).**

- **Only V3 beats buy-and-hold** (Sortino 0.71 vs 0.33; lift +0.38) and is
  the only variant that makes meaningful money net of costs.
- **V1 (simple SMA) is weak** — barely positive, below BAH on Sortino.
- **V2 (Donchian, the "classic CTA" signal) is the worst — it loses money.**
  The Turtle-style breakout got chopped to pieces in the 2010s commodity
  bear; its asymmetric slow exit kept it long into reversals.

This does **not** match "complexity always wins" (Donchian is also
sophisticated and it failed). The cleaner reading: **the vol-normalization
+ relative-strength gate in V3 is what added value**, not signal complexity
per se. V3's "top 50% of trailing range" gate is a momentum-*acceleration*
signal — it keys on risk-adjusted momentum relative to each instrument's own
2-year history, which (a) is not suppressed by back-adjustment carry drift
(so it trades grains, where V1/V2 are quiet) and (b) concentrates exposure
in instruments with genuinely strengthening trends.

## The robustness problem (all variants)

| Variant | 2018-2026 (in-sample) | 2013-2017 (held-out) |
|---|---|---|
| V1 SMA | 0.65 (+5%) | **−0.51 (−3%)** |
| V2 Donchian | −0.07 (−2%) | **−0.88 (−7%)** |
| V3 Momentum | 1.32 (+12%) | **−0.43 (−4%)** |

**Every variant has a NEGATIVE Sortino in 2013-2017.** The signals only
"work" in 2018-2026. This is the central weakness: the apparent edge is
period-specific to the recent window. 2013-2017 was the heart of the
commodity bear (the 2014-16 oil crash); a long/flat trend system either sat
in cash or got whipsawed buying counter-trend rallies.

The 2014-16 oil-bust window shows this starkly: V3 lost **−28.8%** there —
its acceleration gate repeatedly went long energy on bear-market bounces.
V1 (slower SMA) lost only −3% by mostly staying out. So V3's strength in
trending regimes is mirrored by fragility in choppy bears.

## The genuine bright spot: equity diversification

| Variant | Corr with indices strategy (QQQ 50/200 + T-bill OFF) |
|---|---|
| V1 SMA | +0.09 |
| V2 Donchian | +0.12 |
| V3 Momentum | +0.10 |

**All three are near-zero correlated with the equity strategy** — far below
the 0.30 Tier-A threshold. This is the one criterion every variant passes
decisively. A commodity-trend sleeve, even a mediocre standalone one, is a
real diversifier against the locked equity strategy. V3 in particular: a
+5.3% CAGR / 0.71 Sortino sleeve at 0.10 correlation has portfolio value
beyond its standalone metrics.

Cross-variant correlations (V1-V2 0.79, V1-V3 0.69, V2-V3 0.71) are high —
the three trade broadly the same commodity trends, so there's little to be
gained from combining them.

## Per-sector attribution (cumulative contribution, %)

| Variant | CL | NG | HO | RB | GC | SI | HG | ZC | ZS | ZW | Sectors+ |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| V1 SMA | −4 | +20 | −3 | +1 | +16 | +15 | −13 | −2 | +3 | −8 | 2/5 |
| V2 Donch | −5 | −11 | −13 | −1 | +13 | +11 | −4 | −11 | +8 | −23 | 1/5 |
| V3 Mom | +5 | +19 | +14 | +4 | +22 | +22 | +17 | −2 | +11 | −18 | 3/5 |

**Precious metals (GC, SI) carried every variant** — gold/silver had clean
trends in 2010-2026 (2011 bubble, 2019-2020 run, 2024-2026 surge). **Wheat
(ZW) lost money in all three.** V3 is the only variant with positive
contribution across a majority of sectors (energy + metals), but still only
3 of 5 — short of the Tier-A "≥4 sectors" bar.

## Costs / turnover (net figures already reflect these)

| Variant | Ann. turnover | Cost drag/yr |
|---|---|---|
| V1 SMA | 20.6× | 0.78% |
| V2 Donchian | 6.9× | 0.41% |
| V3 Momentum | 14.7× | 0.60% |

Costs are modest (≤0.8%/yr) and not the reason any variant fails — these
are liquid contracts and the vol-targeting keeps turnover reasonable.

## Tier verdict (revised Q3 criteria)

| Variant | Tier | Binding failures |
|---|---|---|
| V1 SMA | **D** | Sortino 0.22 < 0.5; negative in held-out |
| V2 Donchian | **D** | Negative Sortino; loses money |
| V3 Momentum | **C** | Sortino 0.71 (>0.5 ✓) but sub-period min −0.43 (<0.5) fails Tier B; only 3/5 sectors; lift +0.38 (<0.5) |

**No variant reaches Tier A or B on the 2010-2026 data.** V3 reaches Tier C
— "interesting but not deployment-ready," failing on sub-period robustness.

## Decision

**Do NOT deploy commodity trend as a standalone strategy on this evidence.**
But two things keep it alive rather than rejected outright:

1. **V3 (vol-adjusted momentum) is a real, if modest, signal** and a genuine
   equity diversifier (0.10 corr, 0.71 Sortino, +4.2% after-tax). If anything
   from this round earns further work, it is V3 — not the SMA or Donchian
   variants, which can be set aside.

2. **The sample is truncated and hostile.** The missing 2000-2009 block
   contains the strongest historical commodity-trend environment. The verdict
   should be revisited after the Norgate backfill before commodity trend is
   permanently shelved. It is plausible (not certain) that 2000-2009 lifts
   V3 — and possibly V1 — into Tier B.

**Recommended next step (not auto-executed):** either
  (a) revisit M3 (Norgate backfill) to get 2000-2009 + the ICE trio and
      re-run — the highest-value follow-up; or
  (b) shelve commodity trend with V3 documented as the one candidate worth
      resurrecting if/when better data or a multi-strategy ($25k+) context
      arrives.

Per the locked diversifier-search discipline from the equities work, this is
a clean, documented result: **3 commodity-trend variants tested rigorously;
2 fail outright; 1 (vol-adj momentum) reaches Tier C and is a real
diversifier but is not robust across sub-periods on the available sample.**

## What was NOT done / honest limitations

- **No 2000-2009, no Brent/Sugar/Coffee** (Norgate backfill deferred). This
  is the biggest caveat — see above.
- **Trade-level win rate not computed.** The engine is weight-based
  (continuous vol-targeted book), so a discrete per-trade win rate isn't
  naturally defined; daily/period Sortino + attribution used instead.
- **Long/flat only** (per spec). Classic CTA trend is long/short; a
  long/short version would behave differently in bears (could profit from
  the 2014-16 oil crash instead of sitting out). Out of scope this round.
- **Single parameter set per signal** (no tuning, per spec). The verdicts
  are for the locked definitions only.

## Milestone status

| | |
|---|---|
| M1 Databento pull | ✅ |
| M2 Panama back-adjustment | ✅ |
| M3 Norgate backfill | ⏭ deferred |
| M4 Vol module + full-cov targeting | ✅ |
| M5 Three signal variants | ✅ |
| M6 Portfolio backtest engine + costs | ✅ |
| M7 Comparative analysis + tiers | ✅ (this doc) |

Research round complete on the available data.
