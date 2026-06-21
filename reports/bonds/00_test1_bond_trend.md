# Bond Trend Test 1 — Treasury futures as equity-stress diversifier

**Date:** 2026-06-21
**Branch:** claude/commodity-trend-research
**Runner:** `scripts/run_bond_test1.py`
**Raw output:** `RESULTS_test1.txt`
**Universe:** ZN (10yr), ZB (30yr), ZF (5yr) — Databento 2010-2026 (pre-2010
not available; the load-bearing question is post-2020 anyway)
**Signal:** equity-validated 50/200 trend, vol-targeted basket, long-flat,
T-bill OFF, no look-ahead, costs on.

## Verdict: TIER D (fails standalone Sortino) — but it IS a real diversifier

This is a split result that needs both halves stated:

| Locked sub-criterion | Required | Actual | Pass? |
|---|---|---|---|
| Full-sample Sortino | >0.7 (B) / >1.0 (A) | **0.47** | ✗ |
| Sortino > 0.5 (Tier C floor) | >0.5 | 0.47 | ✗ (by 0.03) |
| Correlation with equity | <0.3 (A) / <0.4 (B) | **−0.29** | ✓✓ |
| Non-negative in 2022 | required | **+2.0%** | ✓ |
| Positive in 2018-Q4 | required (A) | **+0.5%** | ✓ |
| Equity-stress windows positive | ≥1 (B) | **4 of 4** | ✓✓ |

**TIER D** — it fails the standalone-Sortino bar (0.47, below even Tier C's
0.5), while passing *every diversification-specific sub-criterion*. It is a
genuine equity-stress diversifier that doesn't generate enough standalone
risk-adjusted return to be deployable on its own.

## The load-bearing test: did bond trend survive 2022? YES.

2022 is the year the bond-diversification thesis broke — buy-and-hold bonds
crashed alongside equities:

| | 2022 return |
|---|---:|
| ZN (10yr) buy-and-hold | **−14%** |
| ZB (30yr) buy-and-hold | **−22%** |
| ZF (5yr) buy-and-hold | **−10%** |
| **Bond TREND (this strategy)** | **+2.0%** (0% drawdown) |

The trend filter went flat/cash on bonds through 2022 and **avoided the
crash entirely**, even eking out +2% from the T-bill leg. This is the
post-2020-regime robustness the test was designed to find — and bond *trend*
passes it where bond *buy-and-hold* catastrophically failed.

## Equity-stress behavior (the diversification evidence)

| Window | Bond trend | Equity (QQQ) | Corr |
|---|---:|---:|---:|
| 2018-Q4 correction | +0.5% | −22.8% | — |
| 2020 March COVID | **+8.0%** | −16.3% | −0.72 |
| 2022 inflation bear | +1.6% | −32.4% | — |
| 2025 Liberation Day | +0.9% | +2.3% | +0.07 |

**Positive in all 4 equity-stress windows**, full-sample correlation −0.29
(genuinely negative). The 2020 COVID +8% with −0.72 correlation is textbook
flight-to-quality hedging. This is *exactly* the crisis profile the portfolio
wanted — the thing crypto and commodities couldn't provide.

## So why Tier D? The whipsaw tax.

Full sample: CAGR +1.2%, Sortino 0.47, MaxDD 9%, 16.4 transitions/yr. The
50/200 trend on bonds **whipsaws heavily** (16×/yr vs ~6×/yr on equities) —
bonds are mean-reverting and choppy, so the trend filter generates many
false signals. In calm periods the transaction costs + small whipsaw losses
roughly offset the crisis-period gains, leaving net returns at ~the T-bill
level. Raising leverage to chase the 10% vol target makes it *worse* (CAGR
goes negative at cap 1.5-3.0) because higher-sized whipsaws bleed faster.

So the honest picture: **bond trend is a crisis hedge that pays off in
equity stress but bleeds slightly in calm periods, netting ~T-bill returns
standalone.** The diversification benefit is real; the standalone
risk-adjusted return is not enough to clear the Sortino bar.

## The deeper finding about bonds-as-diversifier

There's a genuine bind here worth recording:
- **Buy-and-hold bonds** hedge equity stress in *most* regimes (flight to
  quality) but failed catastrophically in 2022 (inflation/rate-shock — bonds
  and equities fell together). That's why the thesis "broke."
- **Trend bonds** avoid the 2022 failure (goes to cash) but whipsaw away the
  return in calm periods.

You can have the 2022 protection (trend) or the steady carry (buy-and-hold),
but not both from a simple bond strategy. The clean, always-on bond
diversifier that survives inflation regimes doesn't appear to exist in this
toolkit.

## Caveats

- **Pre-2010 unavailable** (Databento floor). The 1982-2020 declining-rate
  bull — where bond trend would look spectacular — is excluded. This is a
  *feature* for our purposes: we deliberately tested the hard post-2020
  regime, not the easy tailwind era.
- **Sizing:** verified the Tier D verdict is robust to the weight cap (tested
  0.5 / 1.5 / 3.0; higher leverage only worsens it). Not a sizing artifact.
- **Vehicle:** ZN/ZB/ZF futures are Section 1256 (tax-efficient) and the
  natural instrument; deployable via micro Treasury futures or TLT/IEF/IEI
  ETFs at small size.

## Decision

**Per the locked decision tree: bond trend fails Tier B → trigger Test 2
(FX carry + trend).**

But the nuance matters for that decision: bonds *did* demonstrate the
diversification profile we want (−0.29 corr, 4/4 stress wins, dodged 2022) —
they just don't clear the standalone-Sortino bar because the 50/200 signal
whipsaws on choppy bonds. The question FX must answer is whether *any* asset
gives us diversification **and** a deployable standalone return, or whether
the honest conclusion is that clean crisis-diversifiers with positive
standalone Sortino don't exist in the retail-systematic toolkit.

Recommendation: proceed to Test 2 (FX) per the tree — but go in with eyes
open that we may be looking for something (uncorrelated AND standalone-
profitable) that the bond result suggests is genuinely hard to find.
