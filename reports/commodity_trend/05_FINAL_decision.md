# Commodity Trend Research — FINAL decision & close-out

**Date:** 2026-06-21
**Branch:** claude/commodity-trend-research
**Status:** CLOSED. Research shipped on the 2010-2026 dataset. Norgate
backfill attempted and abandoned (trial cap). No further spend.

## Decision

Ship the **2010-2026, 10-CME-commodity** result as the final deliverable.
The 2000-2009 backfill (and the 3 ICE instruments) are documented as a
known, deliberately-accepted limitation — not pursued further.

## Why the backfill was abandoned

M3 (Norgate backfill) was attempted properly:
1. Built and committed a local `norgatedata` Python pull script
   (`scripts/local_norgate_pull.py`) that bypasses the Exporter GUI.
2. Verified end-to-end on the user's Windows machine: `norgatedata` v1.0.74
   connected to NDU, `price_timeseries('&CL_CCB', ...)` returned clean OHLC +
   OI data. **The pipeline works.**
3. **Blocker:** the Norgate *free trial* is hard-capped at **2 years** of
   history (verified — returned exactly 502 bars back to 2024-06-20 against a
   2000-01-01 request). The cap is the trial restriction itself; no NDU
   setting lifts it.
4. Researched cheaper paid alternatives for pre-2010 daily continuous
   futures: FirstRate (only back to ~2007-2008), EODHD (no clean continuous
   futures; FRED spot only), CSI (comparable-or-pricier than Norgate, which
   resells CSI anyway). **Conclusion: Norgate $270/yr is the cheapest viable
   source; nothing cheaper reaches 2000-2009.**
5. User elected not to spend $270 for a nice-to-have. The script is parked
   and will work immediately if the subscription is ever upgraded.

## The "is 2000-2009 even representative?" point (recorded for the record)

The user's rationale for stopping is methodologically sound and partially
offsets the missing-data concern:

> The commodity market structure of 2000-2009 differs materially from today.
> The 2003-2008 supercycle was driven by China's industrialization shock and
> a pre-financialization futures market. Post-2010, commodity futures became
> heavily financialized (index funds, ETFs, algorithmic flow), correlations
> to risk assets rose, and the roll-yield/carry regime shifted. A trend
> signal validated on 2000-2009 might be validated on a market that no
> longer exists.

This is a real argument, not just rationalization. It means:
- The 2010-2026 window, while *hostile* to trend (a commodity bear), is
  arguably the more *deployment-relevant* regime.
- A signal that works only because of the 2003-2008 supercycle would be a
  fragile thing to deploy into 2026+ markets.
- Conversely, the honest counter-caveat remains: we genuinely do not know
  whether V3 would have reached Tier B with 2000-2009 included, and we
  should not claim otherwise.

Both statements stand together: **the verdict is on the most
deployment-relevant 16-year window; the supercycle era is untested and we
make no claim about it either way.**

## Final research verdict (unchanged from M6/M7)

| Variant | Sortino | CAGR | MaxDD | Corr w/ equities | Tier |
|---|---:|---:|---:|---:|---|
| EW commodity BAH (benchmark) | 0.33 | +2.6% | 70% | — | — |
| V1 Classic 50/200 SMA | 0.22 | +1.2% | 44% | +0.09 | D |
| V2 Donchian 100/50 | −0.19 | −2.6% | 59% | +0.12 | D |
| **V3 Vol-adjusted momentum** | **0.71** | **+5.3%** | **38%** | **+0.10** | **C** |

**Deployment decision: do NOT deploy commodity trend as a standalone
strategy.** No variant reached Tier A/B on the available data.

**One survivor worth remembering:** V3 (vol-adjusted momentum) is a real,
if modest, signal and a genuine equity diversifier (0.10 correlation, well
under the 0.30 bar; +4.2% after-tax CAGR). If commodity exposure is ever
revisited — in a multi-strategy context at $25k+, or if a clean full-history
dataset becomes available — V3 is the one candidate to resurrect. V1 (SMA)
and V2 (Donchian) can be set aside.

## What this round delivered

- A complete, reusable commodity-futures research stack: Databento loader
  with roll-aware caching, Panama back-adjustment, full-covariance
  vol-targeting, three signal modules, a cost-aware portfolio backtest
  engine, and tier classification — all tested (21 passing tests).
- A clean comparative verdict across three trend-signal families.
- Four real data-quality bugs caught and documented (pct_change on
  back-adjusted prices, grain calendar-NaN signal zeroing, covariance
  dropping grains, CME Sunday-session artifacts).
- An honest negative result with one Tier-C survivor and a fully-documented
  data limitation.

## Relationship to the locked equity strategy

The equity strategy (QQQ shares 1x + 50/200 SMA + SGOV OFF) remains the
deployment baseline, unaffected by this research. Commodity trend was
evaluated as a potential diversifier and did not earn a deployment slot.
The ~0.10 correlation finding is filed for the future: if a diversifier is
ever wanted, V3 commodity momentum is a low-correlation candidate, just not
a strong-enough standalone one to deploy today.

## Milestone status — FINAL

| | |
|---|---|
| M1 Databento pull (10 CME) | ✅ |
| M2 Panama back-adjustment | ✅ |
| M3 Norgate backfill | ❌ abandoned (trial 2-yr cap; not worth $270) |
| M4 Vol module + full-cov targeting | ✅ |
| M5 Three signal variants | ✅ |
| M6 Portfolio backtest engine + costs | ✅ |
| M7 Comparative analysis + tiers | ✅ |

**Commodity trend research: CLOSED.**
