# Second Pass — Test 2: Carry + Overall Conclusion

**Date:** 2026-06-21
**Branch:** claude/commodity-trend-research
**Runner:** `scripts/run_commodity_test2_carry.py`
**Raw output:** `RESULTS_test2_carry.txt`

## Test 2 result: carry is Tier D (loses money)

| Metric | Carry standalone |
|---|---:|
| CAGR | **−5.0%** |
| Sortino | −0.39 |
| Max DD | 66% |
| 2018-2026 sub-period | −0.75 (negative) |
| 2013-2017 sub-period | +0.54 |
| Sectors positive | **0 of 4** |
| Annual turnover | **110×** |

The locked carry signal (LONG backwardation, SHORT deep-contango, no
smoothing) loses money on the 2010-2026 CME universe. Two reasons:

1. **Brutal turnover.** 110×/yr — the raw term-structure ratio hovers near
   the zero/−0.5% thresholds and flips constantly. At ~4-8 bps/trade that's
   several %/yr of pure cost drag before any directional view.
2. **The directional bet didn't pay.** Applying carry *direction* to the
   back-adjusted *return* is a bet that backwardation predicts price
   appreciation. On 2010-2026 it didn't hold — spot moves dominated and
   went against the term-structure positioning.

(Methodology note: a "pure" carry harvest — long backwardation / short
contango to capture roll yield as the curve converges — is partly already
embedded in the back-adjusted series. The locked definition tests carry as a
*directional* signal, which is the spec's intent, and it fails. A second look
would add hysteresis/smoothing to tame the 110× turnover and possibly
normalize the threshold by days-to-expiry — but per one-look discipline we
report the locked definition's verdict: Tier D.)

## The critical orthogonality finding

| Correlation | Value | Read |
|---|---:|---|
| Carry vs equity strategy | **−0.04** | uncorrelated |
| Carry vs Test-1 trend | **+0.07** | orthogonal |

Carry is **genuinely a third, orthogonal signal** — uncorrelated with both
the equity strategy and the commodity trend strategy. This is the one thing
the spec flagged as decisive ("if carry is uncorrelated with both, it's a
real third strategy line").

**But orthogonality is worthless without positive expected return.** An
uncorrelated money-loser doesn't diversify anything — it just bleeds. Proof:
the 50/50 trend+carry blend produces Sortino **0.16** (CAGR +0.7%), *worse*
than trend alone (0.67). Carry's negative drift poisons the combination
despite the low correlation.

Per-regime, carry was mixed during equity stress (+12% in 2014-16, +19% in
2022, but −10% in 2018-Q4 and −12% in 2025) — no reliable crisis profile.

## Second-pass scoreboard

| Strategy | Sortino | CAGR | MaxDD | Both sub-periods +? | Corr w/ equity | Tier |
|---|---:|---:|---:|:--:|---:|:--:|
| Test 1 — long-short trend | 0.67 | +5.7% | 27% | ✓ (+0.71, +0.69) | −0.05 | **C** |
| Test 2 — carry | −0.39 | −5.0% | 66% | ✗ (−0.75, +0.54) | −0.04 | **D** |

**Neither cleared Tier B.**

## Conclusion (honoring the pre-committed rule)

The mandate pre-stated the conclusion: *"If neither test clears Tier B, the
honest conclusion is that commodity strategies don't earn their place in our
portfolio under reasonable criteria and we move on."*

By the locked letter, that is the outcome: **move on.** Carry is dead
(Tier D, loses money). Long-short trend is Tier C, missing Tier B.

## The honest nuance (for an informed override)

One thing must be flagged so the "move on" decision is fully informed:

**Test 1 (long-short trend) satisfies the actual second-pass mandate even
though it misses the Tier-B number.** The mandate's own words: *"commodity
strategy needs to provide what equity doesn't — primarily uncorrelated
returns during equity stress, not matching Sortino."* On that axis Test 1
is a clear success:

- Made money in **4 of 5** equity-stress windows (+33% / +11% / +22% / +6%)
- Negative or near-zero correlation in **every** crisis (full-sample −0.05)
- **Both** sub-periods robust (the first-pass failure, fixed)
- Max DD 27%, inside the Tier-A box
- Misses Tier B by **0.03 Sortino (0.67 vs 0.70)** — on the exact metric the
  mandate said to de-emphasize

So there is a genuine tension between two of the mandate's own instructions:
the strict "neither clears Tier B → move on" gate, and the "judge it on
crisis diversification, not Sortino" reframing. Gating on Sortino 0.70 is
itself a Sortino test, which the reframing down-weighted.

## Recommendation

**Two defensible paths; the call is the portfolio owner's:**

1. **Honor the pre-committed rule — shelve commodities (default).** Neither
   test cleared Tier B. Discipline says move on. This is the clean,
   pre-agreed outcome and there is no shame in it: we tested 5 signal
   variants across two passes with rigor, and none cleared the bar. The
   equity strategy remains the sole deployment.

2. **Override on the mandate's spirit — keep long-short trend as a future
   crisis-diversifier sleeve.** Only if/when account size supports
   multi-strategy ($25k+). Test 1 does exactly what was asked of a commodity
   sleeve; the Tier-B miss is 0.03 on a de-emphasized metric. Carry is
   dropped either way.

**My recommendation:** honor the pre-committed rule and **shelve commodity
strategies for now** — but file Test 1 (long-short V3) explicitly as the
"resurrect first" candidate, because at $25k+ in a multi-strategy context its
crisis-diversification profile (positive in 4 of 5 equity crises, −0.05 corr)
is genuinely valuable and clearly the best commodity result of the project.
Carry is closed.

This respects your discipline (you pre-committed to "move on" if neither
cleared Tier B) while making sure the one near-miss that meets the real
mandate isn't lost.

## What a third pass would do (if commodities are ever revisited)

Not recommended now, but documented so the trail is complete:
- **Long-short trend is the foundation** — it works. Build on it, not carry.
- **Smooth/hysteresis the carry signal** to kill the 110× turnover, and test
  it as a *roll-yield harvest* (curve-convergence) rather than a directional
  bet. Carry's orthogonality (+0.07 vs trend) means a *profitable* carry
  variant would genuinely stack.
- **Full history + ICE instruments** (the deferred Norgate $270) for a real
  robustness test across 2000-2009.
- **Long-short on all signal families**, not just V3.

## Milestone status — second pass

| | |
|---|---|
| Test 1 long-short V3 | ✅ Tier C — crisis diversifier, near-miss on Tier B |
| Per-regime correlation analysis | ✅ (the decisive evidence) |
| Test 2 carry | ✅ Tier D — orthogonal but loses money |
| Combined trend+carry sleeve | ✅ worse than trend alone |
| Decision | Shelve per pre-committed rule; Test 1 filed as resurrect-first |

**Second pass complete. Commodity research closed (again), with a clearer
picture: long-short trend is the real candidate, carry is dead, and the
deploy decision is a documented judgment call resolved toward discipline.**
