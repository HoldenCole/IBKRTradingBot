# FX Test 2B — Regime Split (the "is post-2022 different?" test)

**Date:** 2026-06-22
**Branch:** claude/commodity-trend-research
**Runner:** `scripts/run_fx_test2b.py`
**Raw output:** `RESULTS_test2b.txt`
**Hypothesis under test:** the 2A naive-carry failure was partly a ZIRP-era
artifact (suppressed rate differentials → thin carry returns that crashes
exceeded). The 2022+ high-rate regime might produce structurally different
behavior.

## Verdict: REJECT THE HYPOTHESIS. Carry is **worse** post-2022, not better.

| Strategy | Pre-2022 ZIRP Sortino | Post-2022 high-rate Sortino | Delta | Tier (post-2022) |
|---|---:|---:|---:|:--:|
| Carry (long-short basis) | −0.77 | **−0.92** | **−0.14** | D |
| Trend 50/200 (long-flat) | −0.46 | **−1.13** | **−0.67** | D |

Both strategies are **worse** in the post-2022 era than the pre-2022 ZIRP era.
The regime change made carry's diversifier profile slightly *more* negative
(equity correlation went from +0.23 to −0.11), but it deepened the standalone
losses and reduced the stress-window wins from 1/3 to **0/3**.

**This is not "carry just needs higher rates to work."** The data is now
clear: carry loses in stress *regardless* of rate environment. The ZIRP-era
hypothesis was reasonable; the data rejected it.

## What actually changed in the high-rate era (and why it didn't help)

I expected rate hikes to *uniformly* widen FX rate differentials. The basis
data shows that's only partially true — and not in a way that helps carry:

| Pair | Median \|basis\| 2010-2021 | 2022-2026 | Change |
|---|---:|---:|---:|
| 6E (EUR/USD) | 0.20% | **0.42%** | **+0.22pp** |
| 6J (JPY/USD) | 0.17% | **0.89%** | **+0.73pp** |
| 6B (GBP/USD) | 0.10% | 0.05% | −0.05pp |
| 6A (AUD/USD) | **0.35%** | 0.15% | **−0.20pp** |
| 6C (CAD/USD) | 0.14% | 0.19% | +0.05pp |
| 6N (NZD/USD) | **0.29%** | 0.19% | −0.09pp |

**The rate-differential picture flipped, not widened.** Pre-2022 carry was
the textbook AUD/NZD-long, JPY-short trade — AUD and NZD had the biggest
basis, JPY had the most negative. Post-2022 that completely reversed: **JPY
became the most negative-basis currency (basis −0.89% monthly), AUD/NZD
basis compressed dramatically as their central banks cut while the BoJ
held**. So the carry trade post-2022 is still "long-something / short-JPY"
— but the long side is now USD itself (we're trading USD-denominated
futures), so the available carry collapsed to mostly EUR-long / JPY-short
positioning, with much smaller magnitudes.

The hypothesis assumed "more rate differential = more carry." The data shows
the differential is **just rearranged**, with the biggest move being JPY's
basis widening — which is famously the *funding* side of carry, not the
profitable side. And the 2024 yen unwind happened in exactly this widened-
JPY-basis configuration, hitting carry positioning hard.

## Per-stress-window — the structural finding holds

| Stress window | Carry P&L | Equity P&L |
|---|---:|---:|
| **2022 inflation bear** | **−6.9%** | −32.4% |
| **2024-Aug yen unwind** | **−2.0%** | +3.8% |
| **2025 Liberation Day** | **−1.1%** | +2.3% |
| **Carry post-2022 wins: 0 of 3** | | |

All three post-2022 stress windows showed carry losing. The Aug 2024 yen
unwind — the canonical recent FX stress test the spec specifically called
out — hit carry exactly as predicted by the structural failure mode: long
high-yielders / short JPY positioning got unwound, carry lost.

The 2022 inflation bear is the most damning: −6.9% in the year where rate
differentials were supposedly widest. Equity lost −32% same period — carry
correlation was +0.00 in that window, neither hedge nor diversifier.

## The trend result is interesting (but still Tier D)

Trend on FX has a sub-result worth noting:
- Pre-2022: Sortino −0.46, **+0.17 equity correlation**, 1/3 stress wins
- Post-2022: Sortino **−1.13**, **+0.09 equity correlation**, **2/3 stress wins**

Trend stress wins *improved* post-2022 (it went to cash during 2022 and
Liberation Day, eking out small positive returns). But the standalone
Sortino crashed (−1.13). It's a "do nothing" strategy in a costly way —
gives up small whipsaw losses constantly, then sits in cash during the
crises. Tier D regardless.

## Sample-size honesty

- **Post-2022 = 1,162 trading days (4.6 years)** and **3 stress windows**.
  Small. The verdict is "structural failure confirmed across regimes" rather
  than "validated on a small sample" because:
  - The signal direction was confirmed correct (sanity-checked in 2A)
  - The failure pattern matches the well-known FX-carry-as-diversifier
    failure mode (carry crashes in risk-off events)
  - The 0-of-3 stress-window result is unambiguous within the sample
- If post-2022 had shown materially *better* results (e.g., +0.5 Sortino,
  2/3 stress wins), the small sample would warrant caution. **Bad results on
  a small sample are stronger evidence than good results on a small sample**,
  because regime-specific tailwinds wouldn't produce structural losses.

## Decision tree (per the spec)

The spec said: "Report 2B first, then we decide on 2C and 2D."

- **If 2B shows materially better post-2022 results** → run Tests 2C (EM) and
  2D (risk-filtered carry)
- **If 2B shows no regime difference** → structural argument confirmed, skip
  2C/2D
- **If 2B is genuinely ambiguous** → run 2C only

**The result is unambiguous:** post-2022 carry is **worse**, not better. The
structural failure mode (loses in stress) is confirmed across both regimes.
**Per the locked decision tree: skip 2C and 2D.**

The reasoning isn't recency-blindness — it's that the proposed mechanism
("higher rate differentials → more carry to harvest → can survive stress
losses") was rejected by the very test designed to find it. Adding EM
currencies (Test 2C) or VIX filtering (Test 2D) would chase result rather
than mechanism; they'd be moving the goalposts after the hypothesis test
failed.

## What this confirms

The diversifier search closes definitively. Across ~10 candidates tested
under disciplined methodology:

- One near-miss (commodity long-short V3, deferred to $25k+)
- Bonds: real diversification properties but Tier D on standalone Sortino
- FX: failed in both naive form (2A) and regime-split form (2B)
- Everything else: Tier D

**The deployable portfolio remains: equity trend + BTC trend + T-bills as
the implicit diversification mechanism.** During equity bears, both sleeves
sit in T-bills earning yield. That's the honest answer.

## Status

FX Tests 2A + 2B closed. Tests 2C (EM) and 2D (risk-filtered) skipped per
the locked decision tree — the structural argument is confirmed, chasing
the hypothesis further would be result-fitting. Diversifier search closed.
Deployment focus on the equity + BTC sleeves.
