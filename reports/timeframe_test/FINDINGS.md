# Timeframe Variation Test — which signal frequency should deploy?

**Date:** 2026-07-08
**Branch:** claude/commodity-trend-research
**Script:** `scripts/run_timeframe_test.py`  •  **Raw output:** `output.txt`

## Decision (locked criteria applied)

**None of the four variations clears the bar on both sleeves. Daily 50/200
stays as the validated deployment baseline. Proceed with the operational
build as scoped.**

The one-look discipline holds: these four were the test, no sweeping. The
answer is "daily 50/200 is the right timeline."

Two honest nuances worth carrying forward (neither changes the decision):
- **Weekly 50/200 looks best on equity but fails everywhere else that
  matters.** It posts the best full-period equity numbers, but its edge is
  regime-concentrated in bull markets, it is *worse* in the 1966–82 secular
  bear (the regime the strategy exists for), and it is catastrophic on BTC
  (CAGR 21% vs 60%, maxDD −66% vs −43%). A single deployed frequency must
  work on both sleeves; this one does not.
- **Daily 50/200 acted weekly (Var 4) is a performance-neutral whipsaw
  halver.** On *both* assets it matches daily 50/200's risk-adjusted return
  while cutting transitions ~48% and holding after-tax flat-to-better. It
  does **not** clear the "≥+0.3 Sortino OR ≥+0.15 Calmar improvement" bar
  (it's a match, not a beat), so it does not replace daily by the locked
  rule — but it is a legitimate cost-reduction option if operational
  friction ever becomes a concern (see "Optional" below).

---

## Setup

Same framework and conventions as the prior long-history and crypto studies.

- **Equity sleeve:** `^GSPC` (S&P 500, price-only), 1927-12-30 → 2026-04-13,
  98.3 years, 24,686 daily bars. Longest available equity history — the
  deployment's long-history proxy (QQQ itself is only ~26 years; the trend
  rule is validated on ^GSPC, deployed on QQQ).
- **BTC sleeve:** `BTC-USD`, 2014-09-17 → 2026-04-14, 11.6 years, 4,228 bars.
- **OFF vehicle:** FRED **TB3MS** monthly 3-month T-bill → daily compounding
  factor (avg 3.4%/yr full period).
- **No look-ahead (Convention 2):** signal at close[t−1] governs return[t].
  For weekly-acted variants the signal at a Friday close governs the
  *following* week (verified: a Friday-only signal first moves the position
  the next Monday, never same-day).
- **Costs on:** per-transition 5 bps (equity) / 10 bps (BTC) + 0.25%/yr IBIT
  expense while held (BTC). These are the crypto/shares-engine house numbers.
- **Tax (after-tax CAGR):** annual-realization model — risk-asset gains
  realized on exit, short-term (≤365 d) at 37% / long-term at 20%; T-bill
  interest ordinary income; net capital losses carried forward; tax paid from
  the account each year-end (real compounding drag). Pre-tax path reconciles
  with the vectorized equity to <0.001%.

**Caveats.** Price-only indices (both strategy and B&H understate true total
return by the dividend yield equally — relative comparison valid). Weekly
50/200 needs ~200 weekly bars (~3.85 yr) of warmup, which on BTC eats
2014→mid-2018 — a real handicap for that variant on the short crypto history,
and part of why it fails there.

---

## Full-period results

### Equity — ^GSPC, 98.3 yr  (B&H: CAGR +6.3%, Sortino 0.59, Calmar 0.07, maxDD −86%)

| Variation | CAGR | Sortino | Calmar | maxDD | Whip/yr | After-tax CAGR |
|---|---:|---:|---:|---:|---:|---:|
| **1. Daily 50/200 (baseline)** | +5.5% | 0.89 | 0.14 | −38% | 11.39 | +3.7% |
| 2. Weekly 10/40 | +5.1% | 0.80 | 0.14 | −36% | 6.50 | +3.5% |
| 3. Weekly 50/200 | **+6.4%** | **0.97** | **0.26** | **−24%** | **2.33** | **+5.1%** |
| 4. Daily 50/200 acted weekly | +5.3% | 0.84 | 0.13 | −42% | 5.87 | +3.7% |

### BTC — BTC-USD, 11.6 yr  (B&H: CAGR +55.2%, Sortino 1.46, Calmar 0.66, maxDD −83%)

| Variation | CAGR | Sortino | Calmar | maxDD | Whip/yr | After-tax CAGR |
|---|---:|---:|---:|---:|---:|---:|
| **1. Daily 50/200 (baseline)** | +59.6% | 2.07 | 1.38 | −43% | 10.89 | +43.8% |
| 2. Weekly 10/40 | +54.7% | 1.85 | 1.15 | −47% | 5.53 | +41.9% |
| 3. Weekly 50/200 | +21.1% | 1.00 | 0.32 | −66% | 1.21 | +16.7% |
| 4. Daily 50/200 acted weekly | +60.6% | 2.06 | 1.42 | −43% | 5.70 | +44.9% |

---

## Locked criteria evaluation

Replace daily 50/200 **only if all four hold**: (a) ΔSortino ≥ +0.30 **or**
ΔCalmar ≥ +0.15; (b) whipsaw ≥30% fewer transitions/yr; (c) works across all
sub-periods; (d) after-tax CAGR comparable or better.

| Asset | Variation | (a) perf | (b) whipsaw | (c) robust | (d) after-tax | Verdict |
|---|---|---|---|---|---|---|
| Equity | Weekly 10/40 | ✗ (ΔS −0.09, ΔC −0.00) | ✓ −43% | — | ✓ −0.2pp | **FAIL** |
| Equity | Weekly 50/200 | ✗ (ΔS +0.08, ΔC **+0.12** < 0.15) | ✓ −80% | ✗ regime-dep | ✓ +1.4pp | **FAIL** |
| Equity | Daily acted weekly | ✗ (ΔS −0.05, ΔC −0.02) | ✓ −48% | ✓ | ✓ −0.0pp | **FAIL** |
| BTC | Weekly 10/40 | ✗ (ΔS −0.21, ΔC −0.23) | ✓ −49% | — | ✗ −1.9pp | **FAIL** |
| BTC | Weekly 50/200 | ✗ (ΔS −1.07, ΔC −1.06) | ✓ −89% | ✗ | ✗ −27pp | **FAIL** |
| BTC | Daily acted weekly | ✗ (ΔS −0.00, ΔC +0.04) | ✓ −48% | ✓ | ✓ +1.0pp | **FAIL** |

Every variation clears the whipsaw gate (b) — longer/weekly timeframes do
reduce transitions, as hypothesized. **None clears the performance gate (a)
on either sleeve.** The closest is equity Weekly 50/200 at ΔCalmar +0.12,
which misses the +0.15 threshold and then fails robustness (c).

---

## Per-period robustness — why Weekly 50/200's equity edge is a mirage

Sortino by regime (columns = variations 1–4):

| Period | 1 Daily | 2 Wk10/40 | 3 Wk50/200 | 4 Daily·wk |
|---|---:|---:|---:|---:|
| 1928–1949 Depression+WWII | 0.36 | 0.21 | **0.65** | 0.23 |
| 1950–1965 Post-war bull | 1.81 | 1.86 | 1.41 | 1.91 |
| **1966–1982 Secular bear** | **1.86** | 1.60 | **0.94** | 1.57 |
| 1983–1999 Disinflationary | 1.12 | 1.03 | **1.57** | 1.16 |
| 2000–2009 Dotcom+GFC | 0.11 | 0.05 | 0.12 | **0.30** |
| 2010–2017 Post-GFC | 0.33 | 0.65 | **0.79** | 0.45 |
| 2018–2026 Modern | 0.85 | 0.65 | 0.83 | 0.52 |

Weekly 50/200's full-period win comes from the **disinflationary bull
(1983–99: 1.57 vs 1.12)** and **post-GFC bull (2010–17: 0.79 vs 0.33)** —
staying in longer paid off when the trend was smooth and up. But in the
**1966–82 secular bear — the exact regime the trend overlay exists to
handle — it collapses to 0.94 vs daily's 1.86**, because a ~4-year signal
can't react to stagflation-era chop. That is textbook single-regime
dependence, which criterion (c) rules out.

The stress windows confirm it gives back drawdown protection: **1973–74 oil
bear 15% vs daily's 3%**, **2020 COVID 13% vs 5%**, **2022 inflation 11% vs
4%**. The slower signal sits through the early part of every fast selloff.

---

## Whipsaw — the hypothesis was right, but it isn't enough

Transitions/yr, full period: daily 50/200 flips **11.4×/yr** (equity) and
**10.9×/yr** (BTC) — driven by the `close > SMA50` leg crossing often. Every
longer timeframe cuts this materially:

- Weekly 10/40: ~6.5 (equity) / 5.5 (BTC) — ~45–50% fewer
- Weekly 50/200: 2.3 (equity) / 1.2 (BTC) — 80–89% fewer
- Daily acted weekly: 5.9 (equity) / 5.7 (BTC) — ~48% fewer

But whipsaw reduction is only valuable if it doesn't cost risk-adjusted
return. Weekly 10/40 cuts whipsaw and **loses** Sortino on both assets.
Weekly 50/200 cuts the most whipsaw and either fails robustness (equity) or
destroys return (BTC). Only Var 4 cuts whipsaw at true parity — and parity
isn't a "beat."

---

## After-tax — turnover drag is real but not decisive

Annual-realization taxes cost the high-whipsaw daily baseline ~1.8pp/yr
(equity: 5.5%→3.7%) and ~16pp/yr (BTC: 59.6%→43.8%, all short-term on huge
gains). Slower signals recover some of this (equity Weekly 50/200:
6.4%→5.1%, only 1.3pp drag, more long-term treatment). So a whipsaw-reducer
*does* help after tax — but not enough to rescue any variation's failed
performance/robustness gates. Var 4 lands after-tax flat-to-better than
daily on both sleeves (+0.0pp equity, +1.0pp BTC), consistent with "same
returns, fewer taxable events."

---

## Optional: Var 4 as a future cost-reduction lever (not a baseline change)

Daily 50/200 acted weekly is, on this evidence, a **near-free whipsaw
halver**: statistically indistinguishable risk-adjusted performance on both
sleeves, ~48% fewer transitions, marginally better after-tax. It does not
meet the bar to *replace* daily 50/200 (it doesn't improve the signal, it
just trades it less often), so per the locked decision daily 50/200 deploys.
But if 6 months of paper trading shows transaction costs or operational
load higher than modeled, Var 4 is the pre-vetted fallback — same signal,
same infrastructure, executed on Fridays.

---

## Bottom line

Daily 50/200 remains the deployment baseline for **both** the QQQ and BTC
sleeves. The operational build (daily-check job, orchestrator, pending-order
drain) is frequency-correct as scoped — it checks the signal daily and acts
on daily flips. No rework needed. Proceed to the IBKR paper dry-run.
