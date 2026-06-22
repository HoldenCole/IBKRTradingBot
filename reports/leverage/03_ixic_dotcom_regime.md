# IXIC Dot-Com Regime Test — does 50/200 survive 1999-2002?

**Date:** 2026-06-22
**Runner:** `scripts/run_ixic_dotcom_test.py`
**Raw output:** `RESULTS_ixic_dotcom.txt`
**Purpose:** regime-survival proxy. ^IXIC (Nasdaq Composite) used as the
honest free proxy for "NDX-class regime behavior" — 0.99+ correlation with
NDX over the overlapping period, ~31 years of clean Yahoo history (1995-2026)
vs QQQ's 27 years of thinner early-era data. This test asks ONE question:
did the trend filter survive the 1999-2002 dot-com bear, which is the worst
NDX-class drawdown in living memory and is largely absent from our existing
QQQ validation?

This is a regime check, NOT a P&L claim. The deployed vehicle is QQQ shares
(now) / MNQ (later) — IXIC is not tradeable. The strategy's *mechanics*
care about the underlying price action, which IXIC represents well.

## Verdict: REGIME SURVIVAL CONFIRMED

All three locked criteria passed:

| Criterion | Required | Actual | Pass? |
|---|---|---:|:--:|
| Dot-com bear DD < 40% | <40% | **22%** | ✓ |
| 1999 melt-up participation > 50% | >50% | **66%** | ✓ |
| Full-sample Calmar improves vs BAH | trend > BAH | **0.60 vs 0.23** (2.6×) | ✓ |

The filter avoided the catastrophic 78% dot-com drawdown (cut to 22% — saved 56pp).

## Full sample (1995-2026)

| Strategy | CAGR | MaxDD | Calmar | Sortino | Vol |
|---|---:|---:|---:|---:|---:|
| IXIC buy-and-hold | +18% | **78%** | 0.23 | 1.01 | 29% |
| **IXIC 50/200 trend** | +13% | **22%** | **0.60** | 1.31 | 14% |

## Per-era (return / MaxDD)

| Era | IXIC BAH | IXIC 50/200 trend |
|---|---|---|
| 1999 dot-com melt-up | +130% / 13% | **+85% / 15%** |
| **2000-2002 dot-com bear** | **−78% / 78%** | **−21% / 22%** |
| 2003-2007 recovery | +157% / 19% | +42% / 16% |
| **2008 GFC** | **−56% / 55%** | **−7% / 8%** |
| 2009-2014 secular bull | +273% / 19% | +59% / 13% |
| 2015-2017 mid-cycle | +46% / 18% | +13% / 15% |
| **2018-Q4 correction** | **−23% / 23%** | **−2% / 2%** |
| 2019-2020 chop+COVID | +68% / 30% | +13% / 13% |
| 2020-21 retail boom | +39% / 11% | +8% / 14% |
| **2022 inflation bear** | **−33% / 35%** | **−2% / 5%** |
| 2023+ AI/ETF era | +153% / 24% | +78% / 13% |

## What this confirms

The 50/200 trend filter has now been validated across **every major NDX-class
drawdown back to 1995**:
- Dot-com bear 2000-2002 (78% → 22%)
- GFC 2008 (55% → 8%)
- 2018-Q4 (23% → 2%)
- 2020 COVID (within "2019-2020 chop+COVID")
- 2022 inflation bear (35% → 5%)

This is the regime evidence the QQQ-only validation was missing. The
deployment plan's drawdown-control thesis is empirically supported across
the worst recorded NDX-class environment.

## The honest tradeoff (worth flagging)

The filter gives up meaningful upside in long secular bull runs:
- 2003-2007: +42% trend vs +157% BAH (27% participation)
- 2009-2014: +59% trend vs +273% BAH (22% participation)

This is the well-known cost of trend's defensive bias. The Calmar improvement
makes it a clean win on risk-adjusted return, but operators should expect
to underperform buy-and-hold during the multi-year periods where the index
makes new highs uninterrupted. The filter earns its keep specifically
during drawdowns and choppy regimes.

## What this DOESN'T claim

- This is not a P&L claim — IXIC is the spot index, not a tradeable vehicle.
  No commissions, slippage, or roll costs are modeled.
- This doesn't validate the *futures* (NQ/MNQ) vehicle specifically — that's
  the companion test (`04_nq_vehicle_equivalence.md`).
- The 1999-2002 era is uniquely awful — performance there shouldn't be
  extrapolated as a base case. It's a stress-test pass, not a typical
  expectation.

## Implication for deployment

**No change to the deployed plan.** This was a regime-survival check, and
the strategy passed it. The vehicle migration path (QQQ shares → MNQ at
$50k+) and the locked 50/200 signal are confirmed against the worst NDX
regime in 30 years.

The deployed plan now has empirical regime evidence covering:
- 1995-2026 IXIC proxy (~31 years, includes dot-com)
- 1999-2026 QQQ shares (original validation, ~27 years)
- 2010-2026 QQQ + IBKR-tradeable detail
- 1928-2026 ^GSPC (~98 years from the original equity validation, broader index)

That is sufficient regime coverage to deploy with confidence.
