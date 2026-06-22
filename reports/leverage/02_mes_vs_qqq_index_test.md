# MES vs QQQ Index Test — does 50/200 work on SPX as well as NDX?

**Date:** 2026-06-22
**Runner:** `scripts/run_mes_vs_qqq_index_test.py`
**Raw output:** `RESULTS_mes_vs_qqq.txt`
**Verdict:** **NO.** MES is not a like-for-like vehicle swap. **Use MNQ
(NDX futures) at $50k+ instead.**

## The question

The locked deployment uses QQQ 50/200 (Nasdaq-100). MES futures track SPX
(S&P 500) — a *different index*. Switching to MES at the $40k+ vehicle
threshold would be both a vehicle change AND a strategy change. Does the
50/200 rule on SPX produce similar risk-adjusted return to 50/200 on NDX?

## Result

| Strategy | CAGR | MaxDD | Calmar | Sortino | Vol |
|---|---:|---:|---:|---:|---:|
| QQQ buy-and-hold (NDX) | +30% | 36% | 0.85 | 1.68 | 25% |
| SPY buy-and-hold (SPX) | +19% | 34% | 0.55 | 1.29 | 21% |
| **QQQ 50/200 trend (deployed)** | **+12%** | 22% | **0.52** | 1.18 | 14% |
| **SPY 50/200 trend (the test)** | +6% | 23% | **0.27** | 0.86 | 10% |

**SPY trend Calmar (0.27) is half of QQQ trend Calmar (0.52).** SPX trend
makes about half the CAGR for similar drawdown — it works, just less well.

## Locked criteria check

| Criterion | Required | Actual | Pass? |
|---|---|---|---|
| SPX Calmar within 0.20 of NDX | ±0.20 | gap 0.25 | **✗** |
| SPX MaxDD within 5pp of NDX | ±5pp | gap 1pp | ✓ |
| SPX Sortino positive in BOTH sub-periods | required | +1.24 / +0.54 | ✓ |
| Equity-stress windows qualitative match | required | match in all 4 | ✓ |

**Fails on Calmar gap.** SPX 50/200 has identical loss profile but materially
worse return — half the CAGR for similar drawdown. It works as a strategy;
it doesn't work as a like-for-like swap.

## Mechanism — why NDX is the right index for this strategy

Two things mechanically advantage NDX-trend over SPX-trend:

1. **Higher structural drift.** NDX BAH CAGR was +30% vs SPX's +19% over the
   same window — the Nasdaq-100's tech-tilt produced the post-2010 dominant
   bull. The 50/200 trend filter is a long-biased "be invested when the
   trend is up" rule, so it earns more when the underlying drift is bigger.

2. **More persistent trends.** NDX rallies and corrections tend to run
   further (tech momentum / concentration effects). The 50/200 filter is a
   slow signal — it monetizes long persistent moves. SPX's broader index
   produces more mean-reversion / shorter trends, leaving less for the
   filter to capture.

Bears were dampened similarly on both (similar MaxDD, similar
equity-stress-window losses). The difference is on the *upside*, not the
downside. This is consistent with the long-biased framing of the strategy.

## Sub-period and stress consistency

| Period | QQQ trend Sortino | SPY trend Sortino |
|---|---:|---:|
| 2018-2026 in-sample | +1.58 | +1.24 |
| 2010-2017 held-out | +0.72 | +0.54 |

Both robust, both lower for SPX. Equity-stress windows match qualitatively
(both negative or both positive, within ~3pp). This isn't "SPX trend
doesn't work" — it's "SPX trend works, just worse."

## Recommendation

**Do NOT switch to MES at $40k+.** Switch to **MNQ at $50k+ instead.** MNQ
specs from the companion analysis (`01_mes_vehicle_analysis.md`):

- $2 × NDX ≈ $50,000 notional at NDX 25,000
- Margin ~$3,000 overnight
- Same Section 1256 60/40 tax treatment as MES
- **Same NDX-tracking underlying as the deployed QQQ strategy** — a true
  vehicle-only swap

The higher account-size threshold ($50k vs $40k) is the cost of preserving
the strategy edge. ~10pp tax saving plus capital efficiency plus no-wash-sale
are still real at that size, just on a slightly bigger account.

## Updated vehicle decision summary (final)

| Account size | Equity sleeve vehicle | Why |
|---|---|---|
| **$8k - $50k** | **QQQ shares (IBKR Lite, $0 commission)** | MNQ at 1 contract is too big to size cleanly; ordinary-rate tax + wash-sale complexity accepted |
| **$50k+** | **1 MNQ future** | Same NDX strategy; gains §1256 tax (~10pp saving), no wash-sale, capital efficiency. **NOT MES** — MES is a different index and worse Calmar. |
| $200k+ | 1-2 MNQ futures, possibly NQ at ~$1M | Scaling within the same vehicle |

## What we learned (worth keeping for the deployment doc)

- **The 50/200 rule is index-specific.** It works much better on NDX than
  SPX in the 2010-2026 sample. Anyone copying "QQQ 50/200" expecting it to
  work on the broader index will get half the return.
- **The right futures vehicle for this strategy is MNQ, not MES.** Despite
  MES being the more popular / smaller-notional contract.
- **Vehicle decisions ≠ strategy decisions.** It's tempting to assume that
  a tax-efficient futures vehicle is "just a better way to do the same
  thing." When the underlying index differs, that's a strategy change in
  disguise. The empirical test was worth running.

## Status

MES research closed. Recommendation: **stay on QQQ shares until ~$50k; then
switch to MNQ.** Final research queue cleared. Move to deployment focus.
