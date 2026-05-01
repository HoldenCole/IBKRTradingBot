# Phase 1.5 findings — IBS long+short on QQQ shares

**Date:** 2026-05-01
**Period:** 2018-01-01 → 2026-04-15
**Benchmark:** SPY buy-and-hold — return +160.4%, Sharpe 0.70, |DD| 34%

## Engine bug fix (must read first)

While building Phase 1.5, found a bug in `SharesBacktestEngine`'s
short-position handling: cash flow at entry was inverted (subtracting
proceeds instead of adding them) and MTM during open shorts had the
wrong sign. The exit-time math was hacked to compensate, so realized
trade P&L was correct, but the **daily equity curve during open shorts
moved in the wrong direction** — meaning Sharpe ratios in any backtest
involving shorts were wrong.

Phase 1's "with shorts" raw output (Sharpe 0.59 / +83% return) was
computed under the buggy model and is **not directly comparable** to
the corrected Phase 1.5 numbers below. The Phase 1 long-only result
(Sharpe 0.51 / +42%) is unaffected.

Fix in commit on this branch: cash flow on short entry/exit is signed
correctly; MTM contribution of an open short is `−shares × close`
(liability to buy back). Two new tests cover the equity-curve direction
and the cash-delta-equals-pnl invariant.

## Summary table — three variants × three slices

| Variant | Period | N | Sharpe | Total Ret | Max DD | Tier |
|---|---|---|---|---|---|---|
| **L** (long-only) | 2018-2026 | 258 | 0.51 | +42% | −11% | D |
| **S** (short-only) | 2018-2026 | 79 | 0.44 | +29% | −10% | D |
| **LS** (combined) | 2018-2026 | 337 | **0.67** | **+83%** | −16% | D |
| L_train | 2018-2022 | 145 | 0.50 | +24% | −11% | C |
| L_test | 2023-2026 | 113 | 0.50 | +14% | −10% | D |
| S_train | 2018-2022 | 68 | 0.68 | +34% | −10% | C |
| S_test | 2023-2026 | 11 | **−0.26** | −4% | −7% | D |
| **LS_train** | 2018-2022 | 213 | **0.83** | **+66%** | −16% | C |
| **LS_test** | 2023-2026 | 124 | **0.32** | +9% | −11% | D |

Benchmark slices: SPY 2018-2022 +42% / Sharpe 0.44; SPY 2023-2026 +84% / Sharpe 1.30.

## Per-regime split — long vs short contribution (full period)

| Regime | L_n | L_pnl | S_n | S_pnl | Net |
|---|---|---|---|---|---|
| bear (2022) | 3 | −$483 | **46** | **+$3,224** | +$2,741 |
| crisis_recovery (2020) | **44** | **+$2,183** | 6 | +$585 | +$2,768 |
| bull (4 yrs) | 144 | +$2,468 | 13 | −$739 | +$1,729 |
| bull_chop (2025) | 27 | +$524 | 6 | +$574 | +$1,098 |
| chop_to_correction (2018) | 34 | −$526 | 6 | −$352 | −$878 |
| mixed (2026) | 6 | −$372 | 2 | −$413 | −$785 |

The long branch handles bulls and crisis recoveries. The short branch is
**almost entirely a 2022 phenomenon** — 46 of 79 short trades fired in
2022, contributing nearly all the short-side P&L. In bulls, shorts barely
fire (close < SMA200 filter blocks entries) and lose money when they do.

## The mechanistic answer to "why shares-shorts work where ETF-options-shorts didn't"

Earlier (v1.0) backtest: SQQQ ATM-call shorts on the same IBS-overbought
signal lost catastrophically. 2 trades, both stopped out at −50% premium.

Phase 1.5: QQQ shares shorts on the same IBS-overbought signal produced
68% win rate over 79 trades, +$3,224 in 2022 alone, Sharpe 0.44 over 8 years.

**The difference is the option overlay, not the directional signal.**
- The directional signal (IBS > 0.80, close < SMA200) does have edge —
  it correctly identifies overbought prints in downtrends that mean-revert.
- Translating the signal to SQQQ ATM calls layers two costs on top of the
  directional bet: IV crush after vol spikes (which is when the signal
  fires) and theta decay over multi-day holds. Together they convert a
  +PF-1.89 directional bet into a −100% return on premium.

**Generalizable lesson**: directional signals on shares preserve their
edge; same signals routed through inverse-ETF options destroy it. Future
strategy design should default to direct expression unless leverage is
explicitly required AND the holding period is short enough to not be
eaten by theta.

## Walk-forward — meaningful degradation

| Variant | Train (2018-2022) Sharpe | Test (2023-2026) Sharpe | Δ |
|---|---|---|---|
| L | 0.50 | 0.50 | 0.00 |
| S | 0.68 | **−0.26** | **−0.94** |
| LS | **0.83** | **0.32** | **−0.51** |

The long branch is robust (0.50 → 0.50 across the split). The **short
branch is regime-dependent** — Sharpe 0.68 when bear regimes are present
(2022), Sharpe −0.26 in their absence. The combined strategy inherits
the short branch's regime-dependence, dropping from Tier C (0.83) in
train to Tier D (0.32) in test.

## Decision rule application

The user's Phase 1.5 rule:
- Tier B (Sharpe > 1.0, |DD| < 35%, return ≥ SPY): deployable. Phase 2 optional.
- Tier C: proceed to Phase 2.
- Neither Tier C: stop on IBS, pivot to Phase 5.

Strict reading (full period): LS Sharpe 0.67, |DD| 16%, return +83% vs SPY +160%. Sharpe in [0.5, 1.0), |DD| < 35%. **Return fails Tier C constraint** (need ≥ SPY−20% = +140%; have +83%). Strictly **Tier D**.

Train slice: LS Sharpe 0.83, return +66% vs SPY +42%. **Tier C** (cleanly — beats SPY absolute return in the train period).

Test slice: LS Sharpe 0.32, return +9% vs SPY +84%. **Tier D**.

## Honest verdict

**The strict rule says stop. The data doesn't unambiguously say stop.**

What the data says:
1. The IBS LONG signal on QQQ shares is robust — 0.50 Sharpe in/out-of-sample. Real but small edge.
2. The IBS SHORT signal on QQQ shares is **regime-dependent** — works in bear regimes, dead in bulls. The 2022 contribution dominates the 8-year story.
3. The combined Sharpe over 8 years (0.67) is approaching SPY's (0.70) at half the drawdown (−16% vs −34%). That's a real risk-adjusted result, even if it can't compound past SPY in absolute terms at $8k 1-share-at-a-time sizing.
4. Walk-forward degradation in the combined version (0.83 → 0.32) is the most damning signal — without bear regimes the strategy doesn't earn its keep.

What the data doesn't say:
1. The strategy is dead. It works in roughly the regime types it should (mean-reversion buys on oversold dips in trends, short rallies in downtrends).
2. Options leverage couldn't help. With 0.67 Sharpe and −16% max DD, applying 2x leverage gets us to ~+166% absolute return at Sharpe 0.67 and −32% max DD. **That ties or beats SPY on absolute return at acceptable risk.** Phase 2 is exactly the test for whether this works.

## Three options

**Option 1 — Stop on IBS, pivot to Phase 5 (strict rule).** The walk-forward test period is unambiguously Tier D. The strategy may have worked in the past but not forward. Phase 5 (afternoon reversion) and the regime filter become the next workstreams.

**Option 2 — Proceed to Phase 2 cautiously, LS combined (spirit of rule).** The combined Sharpe is borderline-Tier-C, half SPY's drawdown, with a clear mechanistic story. Phase 2 explicitly tests whether leverage closes the absolute-return gap. Failure case is clean — Phase 2 with LS that doesn't clear Tier B → stop.

**Option 3 — Proceed to Phase 2 with LONG-only.** The long branch is the only piece with stable in-sample/out-of-sample Sharpe. Add Phase 2's B0 (modest leverage) test specifically here. If 2x leverage on the long branch gets to ≥SPY return at acceptable Sharpe, we have a candidate. Cleaner than carrying the regime-dependent short.

## My recommendation

**Option 3.** Reasoning:

1. The short branch's degradation in test (Sharpe −0.26) is real and concerning. We're choosing whether to keep a strategy whose primary edge in the past 4 years has dissipated. Going forward I wouldn't bet on it.

2. The long branch is the genuinely robust piece. 0.50 Sharpe in train AND test is what you want to see — a stable, non-regime-dependent signal.

3. Phase 2 was designed to test "can options/leverage rescue an absolute-return shortfall." The long branch presents that question cleanly. Adding the short branch contaminates the test with regime-dependence that confuses interpretation.

4. The shares-shorts mechanistic finding is valuable enough to document and remember without needing to deploy it. Future strategies that use leverage on directional signals should default to direct expression (shares or futures), not inverse-ETF options.

5. If long-only-with-leverage doesn't clear Tier B in Phase 2, the IBS workstream is done and we pivot. Cleaner stop point.

If you'd rather keep the short branch in (Option 2): the per-regime split shows the bear contribution is real. We'd just be betting the next 4 years include another bear regime within the strategy's lifetime.

## Awaiting your call

1. Stop on IBS, pivot to Phase 5
2. Phase 2 with LS combined
3. Phase 2 with long-only (my pick)

Raw output preserved at `reports/phase1_5/raw_output.txt`. Reproducible
via `python scripts/run_phase1_5.py`.
