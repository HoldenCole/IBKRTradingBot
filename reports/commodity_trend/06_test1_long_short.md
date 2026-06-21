# Second Pass — Test 1: Long-Short V3 (vol-adjusted momentum)

**Date:** 2026-06-21
**Branch:** claude/commodity-trend-research
**Runner:** `scripts/run_commodity_test1_ls.py`
**Raw output:** appended to `RESULTS_raw_output.txt` lineage

## TL;DR

Removing the long-flat restriction on V3 **fixed the robustness problem**
that sank the first pass, and the strategy delivers **textbook equity-crisis
diversification**. On the locked letter it lands **Tier C** — but only
because Sortino (0.67) misses the Tier-B threshold (0.70) by 0.03, on the
exact metric the second-pass mandate explicitly de-emphasized. On the metric
that mandate emphasized (uncorrelated returns during equity stress), it is
excellent.

## Headline (full sample, net of costs)

| Metric | Long-short V3 | Long-flat V3 (1st pass) |
|---|---:|---:|
| Sortino | 0.67 | 0.71 |
| CAGR | +5.7% | +5.3% |
| After-tax CAGR | +4.6% | +4.2% |
| Max drawdown | **27%** | 38% |
| Vol | 14% | 12% |
| **2018-2026 sub-period Sortino** | **+0.71** | +1.32 |
| **2013-2017 sub-period Sortino** | **+0.69** | **−0.43 (FAILED)** |

Accounting note: the long-short book uses **futures-collateral accounting**
(capital earns the T-bill rate; the vol-targeted long/short futures book is
an overlay). The long-flat first pass used "idle capital earns T-bill." So
the two Sortinos aren't a perfectly clean comparison — but on the dimension
that matters (robustness), the long-short version is unambiguously better:
it turned the −0.43 held-out failure into +0.69.

## Why long-short fixed robustness

The first-pass long-flat V3 was negative in 2013-2017 because it could only
sit in cash or whipsaw-buy counter-trend rallies during the commodity bear.
The long-short version **shorts the downtrends** — so the 2014-16 oil crash
(crude $107 → $26) became a profit centre instead of a drawdown. Both
sub-periods are now positive (+0.71, +0.69), satisfying the locked
robustness criterion.

## THE KEY TEST: per-regime correlation with the equity strategy

This is what the second-pass mandate actually cares about — not full-sample
Sortino, but behavior *during equity stress*.

| Regime | Commodity return | Equity strat return | Corr |
|---|---:|---:|---:|
| Full sample | — | — | **−0.05** |
| 2014-16 oil crash | **+33.5%** | −8.4% | −0.06 |
| 2018-Q4 correction | **+11.5%** | −3.0% | +0.12 |
| 2020 March COVID | **+22.4%** | −8.2% | −0.11 |
| 2022 inflation bear | **+6.5%** | −3.4% | +0.01 |
| 2025 Liberation Day | −5.2% | −1.5% | −0.03 |

**In 4 of 5 equity-stress windows the commodity strategy MADE money** — and
substantially (+33%, +11%, +22%, +6%) — while equities fell. Correlation is
negative or near-zero in *every* crisis (max +0.12). The one losing regime
(2025 Liberation Day, −5.2%) was still uncorrelated (−0.03) and a small loss.

This is exactly the crisis-diversification profile the mandate asked for:
not "uncorrelated on average but correlated when it counts," but genuinely
uncorrelated *and frequently positive* precisely when the equity book is
under stress. The 2020 COVID and 2022 inflation results are the standouts —
the two regimes where a diversifier earns its keep.

## Per-sector attribution

| Sector | Contribution |
|---|---:|
| Energy | +59.6% |
| Precious | +34.3% |
| Industrial | +24.3% |
| Grains | −23.4% |

3 of 4 sectors positive (energy, precious, industrial). Wheat (−22.7%) is
the main drag again; grains remain the weak sector for this signal. Energy
became a major positive contributor under long-short (vs mixed in the
long-flat pass) — the ability to short energy in 2014-16 is most of why.

## Diagnostics

- Avg active positions/day: 5.4 (vs 3.4 long-flat — shorts add exposure)
- Median gross |exposure|: 1.04
- Annual turnover: 32.7× · cost drag 1.22%/yr (higher than long-flat's 0.6%
  — more positions, more flips — but still not the binding constraint)

## Tier verdict (second-pass locked criteria)

| Criterion | Threshold (A / B) | Actual | A? | B? |
|---|---|---:|---|---|
| Sortino | >1.0 / >0.7 | **0.67** | ✗ | **✗ (by 0.03)** |
| Max DD | <30% / <35% | 27% | ✓ | ✓ |
| Corr with equity | <0.3 / <0.4 | −0.05 | ✓ | ✓ |
| Both sub-periods +Sortino | required | +0.71, +0.69 | ✓ | ✓ |
| Sectors positive | ≥3 / ≥2 | 3 | ✓ | ✓ |

**TIER C** — by the locked letter, because Sortino 0.67 < 0.70. Every other
criterion clears Tier **A**.

## Honest interpretation

This is a real tension worth stating plainly:

- **By the locked numeric letter:** Tier C. The decision tree says "fails
  Tier B → run Test 2 (carry)."
- **By the second-pass mandate's own logic:** the strategy does exactly what
  was asked. The reframing said "commodity strategy needs to provide what
  equity doesn't — primarily uncorrelated returns during equity stress, not
  matching Sortino." On that axis it is excellent (−0.05 full-sample corr;
  positive in 4 of 5 equity crises; both sub-periods robust; 27% DD inside
  the Tier-A box). It misses Tier B *only* on the Sortino metric the mandate
  explicitly down-weighted, and only by 0.03.

I will **not** tweak parameters to push Sortino over 0.70 — one-look
discipline holds; the number is the number.

The strategic read: this is the strongest commodity result of the whole
project and the first one that is genuinely *deployable* as a crisis
diversifier. Whether to (a) accept it now, (b) run Test 2 (carry) per the
tree to see if a second uncorrelated line strengthens the sleeve, or
(c) stop — is a judgment call that belongs to the portfolio owner, which is
why this reports back rather than auto-proceeding.

## Recommendation

**Run Test 2 (carry) before deciding.** Reasoning:
1. The decision tree says to (Test 1 is Tier C, fails Tier B).
2. Carry is cheap now — the second-month data is already cached (from M2),
   infrastructure exists, it's one more run.
3. Carry is *mechanically* uncorrelated with trend. If it's also uncorrelated
   with both the equity strategy AND this long-short trend line, it would be
   a genuine third return stream — and a trend+carry commodity sleeve is a
   materially stronger proposition than trend alone.
4. Nothing is lost: long-short V3 stays on the table as a Tier-C-but-
   mandate-satisfying candidate regardless of how carry does.

Then make the deploy decision with both results in hand.
