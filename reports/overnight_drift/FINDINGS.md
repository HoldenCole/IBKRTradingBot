# Overnight drift — UPDATED FINDINGS (with benchmark lift)

**Date:** 2026-05-02 (revision)
**Supersedes:** initial finding from earlier today that suggested overnight
drift could slot as Component #2.

## The decisive table — Sortino lift over same-period buy-and-hold

The user's instinct was correct: **the 0.29 → 1.14 train-to-test
Sortino jump was the underlying's regime, not strategy edge.** Computing
the same-period buy-and-hold Sortino for the SAME underlying in the
SAME slice eliminates the regime confound:

| Variant | Bench Sortino | Strat Sortino | **Lift** | Bench Return | Strat Return | Lift (pp) |
|---|---|---|---|---|---|---|
| SPY_full | 0.85 | 0.31 | **−0.54** | +160% | +25% | −135 |
| SPY_train | 0.53 | 0.22 | −0.31 | +42% | +10% | −33 |
| SPY_test | **1.77** | 0.56 | **−1.21** | +84% | +13% | −71 |
| QQQ_full | 1.08 | 0.55 | **−0.52** | +302% | +60% | −242 |
| QQQ_train | 0.68 | 0.29 | −0.40 | +68% | +14% | −54 |
| QQQ_test | **2.07** | 1.14 | **−0.93** | +141% | +39% | −102 |

(All figures with realistic 1bp/side slippage on MOC/MOO fills.)

**Sortino lift is negative in every variant.** The QQQ_test number
that looked great in isolation (Sortino 1.14) is dwarfed by QQQ
buy-and-hold's 2.07 over the same period — buy-and-hold beat overnight
drift by 0.93 Sortino and 102 percentage points of return.

The strategy's apparent train-to-test improvement was a recent-bull
artifact. QQQ buy-and-hold also went from Sortino 0.68 (train) to
2.07 (test) — even more dramatically.

## Verdict — overnight drift is dropped

Per the user's stated rules:

> Beat SPY buy-and-hold absolute return — secondary requirement.
> Beat SPY's buy-and-hold Sharpe by a meaningful margin.

Overnight drift does neither, on either underlying, in any slice. It
captures roughly 30-50% of the buy-and-hold return at slightly lower
max drawdown but produces a strictly worse risk-adjusted result than
just holding the underlying.

Even adopting the multi-strategy "component" framing, overnight drift
fails:

- It cannot replace buy-and-hold (worse Sortino, worse return).
- It cannot diversify a long-equity book — it IS long-equity, just
  with 16-hour exposure instead of 24.
- The drawdown profile is essentially identical to buy-and-hold
  (29-31% vs 34-36%).

There is no portfolio role this strategy plays better than direct
share ownership of the same instrument.

## What we learned (worth keeping)

1. **The published overnight-drift edge is real but small.** Win rates
   54-57% pre-cost match academic literature. The signal exists.
2. **Slippage compounds and dominates.** 1bp/side over 2081 round
   trips drags Sortino by 0.4-0.5. Live MOC/MOO fill quality matters
   more than the underlying signal at this trading frequency.
3. **Benchmark comparison is essential.** Standalone Sortino numbers
   like 1.14 look great until compared to the asset they're supposedly
   improving on. Always run the lift comparison.
4. **The infrastructure built is reusable.** OvernightDriftEngine,
   benchmark/lift computation, walk-forward — all generic enough to
   apply to the next candidate.

## What this changes upstream

The overnight drift result was the second consecutive negative finding
on the IBS-style "long-biased mean-reversion or always-long equity"
family of strategies. Combined with:

- IBS-on-shares: Tier D standalone, can't clear Tier C with simple
  regime filter. Even hindsight year-exclusion doesn't beat SPY return.
- Overnight drift: Negative Sortino lift vs buy-and-hold on same instrument.

The pattern is: **strategies that are flavors of long-equity-on-SPY/QQQ
cannot beat just holding SPY/QQQ.** This isn't a strategy-design problem;
it's a structural fact about the 2018-2026 sample, which was dominated
by a strong bull market broken by short crashes that recovered quickly.

The portfolio framing the user articulated is more important than ever:
**any candidate going forward must either beat buy-and-hold of the same
instrument, OR provide a genuinely uncorrelated return stream.**
Long-biased equity strategies have to hurdle SPY/QQQ. Diversifying
strategies have to be measurably uncorrelated.

## Status

- Overnight drift on SPY: **dropped**.
- Overnight drift on QQQ: **dropped**.
- Code preserved at `src/backtest/overnight_engine.py` and tests for
  future reference / reuse on other instruments where the relationship
  to buy-and-hold may differ.

## Next priorities (per user direction)

1. Phase 5 (afternoon reversion) when IBKR puller finishes — likely
   another long-biased-equity candidate, will be evaluated with the
   same lift-vs-benchmark rigor as overnight drift.
2. Scope a genuinely diversifying candidate. VIX spike fade is the
   leading candidate per user. See
   `reports/diversifier_candidates/VIX_SPIKE_FADE_SCOPE.md`.
3. Regime model integration when delivered.
