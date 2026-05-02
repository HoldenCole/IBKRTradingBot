# Sortino addendum — Phase 1 + Phase 1.5 re-evaluation

**Date:** 2026-05-02
**Source data:** `reports/phase1/raw_output_long_only_v2_sortino.txt`,
`reports/phase1_5/raw_output_v2_sortino.txt`

## What changed

1. `equity_metrics_subset()` slices the equity curve by a date predicate
   so per-year and per-regime Sortino can be computed from any backtest
   result without re-running.
2. `format_v2_report()` emits Sharpe AND Sortino in per-year and per-regime
   tables (previously only in headline).
3. `tier.classify()` accepts an optional `strategy_sortino` parameter and
   treats Sharpe OR Sortino as qualifying — whichever is HIGHER. The
   numerical thresholds are unchanged (Tier A: max(Sharpe, Sortino) > 1.5;
   Tier B: ≥ 1.0; Tier C: ≥ 0.5).

## Headline metrics with Sortino

### Phase 1 — IBS on shares

| Variant | Period | N | Sharpe | **Sortino** | Total Ret | |DD| | Tier (new) |
|---|---|---|---|---|---|---|---|
| A1 (SPY) | full 8yr | 208 | −0.04 | −0.02 | −3.6% | 21% | D |
| A1 SIG-ONLY | full 8yr | 203 | 0.03 | 0.01 | −0.3% | 18% | D |
| A1 train | 18-22 | 113 | −0.19 | −0.09 | −7.6% | 21% | D |
| A1 test | 23-26 | 95 | 0.28 | 0.19 | +4.5% | 5% | D |
| A2 (QQQ) | full 8yr | 258 | 0.51 | **0.33** | +42% | 11% | D |
| A2 SIG-ONLY | full 8yr | 248 | 0.43 | 0.29 | +36% | 15% | D |
| A2 train | 18-22 | 145 | 0.50 | 0.30 | +24% | 11% | C |
| A2 test | 23-26 | 113 | 0.50 | 0.39 | +14% | 10% | D |

### Phase 1.5 — IBS long+short on QQQ shares

| Variant | Period | N | Sharpe | **Sortino** | Total Ret | |DD| | Tier (new) |
|---|---|---|---|---|---|---|---|
| L | full 8yr | 258 | 0.51 | 0.33 | +42% | 11% | D |
| S | full 8yr | 79 | 0.44 | 0.28 | +29% | 10% | D |
| **LS** | full 8yr | 337 | **0.67** | **0.59** | +83% | 16% | D |
| L_train | 18-22 | 145 | 0.50 | 0.30 | +24% | 11% | C |
| L_test | 23-26 | 113 | 0.50 | 0.39 | +14% | 10% | D |
| S_train | 18-22 | 68 | 0.68 | 0.49 | +34% | 10% | C |
| S_test | 23-26 | 11 | −0.26 | −0.14 | −4% | 7% | D |
| **LS_train** | 18-22 | 213 | **0.83** | **0.72** | +66% | 16% | C |
| LS_test | 23-26 | 124 | 0.32 | 0.30 | +9% | 11% | D |

## Sortino vs Sharpe — what the numbers actually say

**Sortino is consistently LOWER than Sharpe** across every IBS variant.
This is the opposite of the user's expected direction ("things may move
up a tier with Sortino"). Mechanism:

- IBS strategies have **negative skew**: many small, fast wins (typical
  win = 0-day reversion bounce, ~$50) and occasional larger losses
  (typical loss = trade dragged through 5d time stop, ~$130-200).
- Sortino punishes the downside-only deviation. With negative skew,
  downside std > upside std, so Sortino < Sharpe.
- For **positive-skew** strategies (e.g., trend-following, vol selling
  with hedges), Sortino > Sharpe. Not these.

**No tier verdicts changed under the Sharpe-OR-Sortino rule.** Every
strategy that was Tier D under Sharpe is still Tier D. The rule is
permissive in principle, but didn't help here because Sharpe was
always the higher of the two.

## Per-regime Sortino on LS_full — interesting story

| Regime | N | PF | Sharpe | **Sortino** | tier-equiv |
|---|---|---|---|---|---|
| crisis_recovery (2020) | 50 | 3.64 | 2.43 | **1.50** | A |
| bear (2022) | 49 | 1.89 | 1.31 | **1.85** | A |
| bull (4 years) | 157 | 1.23 | 0.79 | **1.81** | A |
| bull_chop (2025) | 33 | 1.51 | 0.80 | 0.82 | C |
| chop_to_correction (2018) | 40 | 0.68 | −0.76 | −0.65 | D |
| mixed (2026) | 8 | 0.41 | −1.50 | −1.56 | D |

**This is the regime-filter case made concrete.** Three regimes
(bull, bear, crisis_recovery) have tier-A-quality Sortino in isolation.
The two bad regimes (chop_to_correction, mixed) have negative Sortino
and drag the overall metric down. If a regime classifier could reliably
identify and exclude the bad regimes (~12% of the 8-year period), the
overall LS_full Sortino would lift materially.

The bull-regime Sortino of 1.81 is the surprise — IBS works in bulls
when long-side dominates, not just the headline-grabbing 2020/2022
periods.

## Decision rule application (user's third ask)

User's rules in priority order:

> If LS combined clears Tier B on Sortino terms → that's the strategy.
> Skip Phase 2 options work entirely, deploy on shares.

LS_full: max(Sharpe 0.67, Sortino 0.59) = 0.67. Tier B threshold = 1.0.
**Does NOT clear Tier B.**

> If long-only clears Tier C on Sortino terms but LS combined doesn't →
> Phase 2 with long-only as planned.

L_full: max(0.51, 0.33) = 0.51. Tier C threshold = 0.5 (clears) AND
return ≥ SPY−20% (need +140%; have +42% → fails).
**Does NOT clear Tier C** (return constraint).

> If neither clears Tier C → pivot to Phase 5 (afternoon reversion) as
> the next strategy candidate, or rethink the whole signal family.

**This is the path the data forces.** Strict reading of the rule.

## My recommendation (not strictly part of the rule, but worth flagging)

The strict-rule answer is "pivot to Phase 5." I'd add the multi-strategy
framing the user articulated and break it into three parallel
workstreams instead of sequential:

1. **Phase 5 (afternoon reversion)** — start as soon as the IBKR 5-min
   puller finishes. Independent strategy candidate.

2. **Build the regime filter** in parallel — the per-regime Sortino
   data above shows clear evidence that IBS-on-shares is a strong
   strategy in 3 of 6 regimes (Sortino 1.50-1.85 in those) and a poor
   strategy in 2 of 6. A working regime filter could elevate IBS from
   Tier D as a standalone to a viable portfolio component.

3. **Defer Phase 2 (options leverage on IBS)**. Leverage doesn't fix
   the regime-dependence problem. If the regime filter works, leverage
   becomes interesting again; if it doesn't, leverage was always going
   to fail. Phase 2 returns to the queue *after* regime-filter
   validation, not before.

This reframes the goal from "make IBS work standalone" (which the data
says won't reach Tier B) to "build a 2-3 strategy book where each
component has tier-C+ in its operating regime." That's the path to
sustainable Sortino > 1.0 at the portfolio level.

## What gets dropped or paused

- **Phase 2 (options leverage on IBS)** — paused. No data signal that
  options translation closes the absolute-return gap meaningfully when
  the underlying signal is regime-dependent. Re-evaluate after regime
  filter exists.
- **B0 (margin leverage on shares)** — paused for the same reason.
  Margin leverage on a regime-dependent strategy amplifies regime
  dependence; it doesn't fix it.

## What proceeds in parallel

- **Phase 5** — afternoon reversion. Starts once `data/intraday/` cache
  is populated by the IBKR puller. Will use the same v2_report +
  benchmark + tier infrastructure already in place.
- **Regime classifier prototype** — design and backtest. The user has
  been building a regime filter separately; this is the moment to
  integrate it. Test: does applying the filter to the existing
  LS_full backtest produce a tier C/B result?
- **IBKR 5-min puller** — already running on user's machine.

## Summary

| Decision rule | Answer |
|---|---|
| LS clears Tier B on Sortino? | **No** (max 0.67 < 1.0) |
| L clears Tier C on Sortino? | **No** (return constraint) |
| Neither clears Tier C → pivot? | **Yes** |

| Workstream | Status |
|---|---|
| Phase 2 (options leverage on IBS) | **paused** |
| Phase 5 (afternoon reversion) | **start when 5-min cache ready** |
| Regime filter on IBS-LS | **start now, in parallel** |
| Multi-strategy portfolio thinking | **adopted as new framing** |
