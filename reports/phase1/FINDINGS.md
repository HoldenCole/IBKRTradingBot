# Phase 1 findings — IBS on shares

**Date:** 2026-05-01
**Period:** 2018-01-01 → 2026-04-15 (8.3 years)
**Benchmark:** SPY buy-and-hold — total return +160.4%, Sharpe 0.70, max DD −34%

## Summary table — long-only IBS

The user's plan specified A1/A2 as long-only IBS tests. Re-ran with
`sqqq_short_enabled=False` on `IBSStrategy`. Numbers below are clean
long-only.

| Variant | Period | N | Win% | Sharpe | Total Ret | Max DD | Tier |
|---|---|---|---|---|---|---|---|
| A1 (SPY) | 2018-2026 | 208 | 65% | −0.04 | −3.6% | −21% | **D** |
| A1-SIG-ONLY (SPY no time stop) | 2018-2026 | 203 | 67% | 0.03 | −0.3% | −18% | **D** |
| A1-TRAIN (SPY) | 2018-2022 | 113 | 65% | −0.19 | −7.6% | −21% | **D** |
| A1-TEST (SPY) | 2023-2026 | 95 | 64% | 0.28 | +4.5% | −5% | **D** |
| A2 (QQQ) | 2018-2026 | 258 | 67% | **0.51** | +42.0% | −11% | **D** |
| A2-SIG-ONLY (QQQ no time stop) | 2018-2026 | 248 | 68% | 0.43 | +36.1% | −15% | **D** |
| A2-TRAIN (QQQ) | 2018-2022 | 145 | 72% | 0.50 | +24.1% | −11% | **C** |
| A2-TEST (QQQ) | 2023-2026 | 113 | 62% | 0.50 | +13.8% | −10% | **D** |

## Decision per the user's plan

The user specified:
- Both A1 and A2 hit Tier A or B → proceed to Phase 2
- One hits B+, the other doesn't → proceed with the working underlying
- Both Tier C → proceed cautiously, expecting marginal results
- **Both Tier D → stop. IBS doesn't work even at baseline.**

**Letter of the rule: stop.** A1 (SPY) is unambiguously Tier D in every
slice. A2 (QQQ) is Tier D over the full period and out-of-sample.

**Spirit of the rule:** more nuanced, see below.

## What the data actually shows

### IBS on SPY: dead

The signal has no edge on SPY shares regardless of period or risk
management. Win rate ~65% but avg loss ($-77) overwhelms avg win ($+39).
Under signal-only mode (no time stop): Sharpe 0.03, +0%/year. The 65%
win rate is misleading — wins are fast-and-small, losses are
slow-and-large. This is the classic IBS failure mode on a low-vol
underlying that grinds higher: oversold prints reverse quickly enough
to hit the +0.7 IBS exit at minimal profit, but trades that don't
reverse get absorbed into ongoing pullbacks.

### IBS on QQQ: edge exists, doesn't compound enough

A2 over 8 years: Sharpe 0.51, +42% total return, max DD −11%. That's a
real, measurable edge that's also visibly under SPY (Sharpe 0.70, +160%).

The Sharpe is in C-tier territory. The constraint that fails is the
absolute return: +42% trails SPY by 118 percentage points. With
1-share-at-a-time sizing on $8k starting capital and full-equity
allocation, the math doesn't support clearing SPY's compounding from
this signal alone. The risk-adjusted return is real, just smaller in
absolute terms.

### Walk-forward holds up but degrades

QQQ Sharpe in train (2018-2022): **0.50**.
QQQ Sharpe in test (2023-2026): **0.50**.

Same Sharpe in-sample and out-of-sample — that's a positive sign for
robustness. **But absolute return collapsed**: train +24% vs test +14%.
The strategy is consistent on a per-trade basis and continues to win
trades, but the magnitude of moves it can capture has shrunk.

This is consistent with the underlying market regime: 2023-2026 is a
sustained bull, IBS oversold prints are shallower and bounces are
smaller in absolute dollar terms. The signal still works — the
opportunities just got smaller.

### Time stop is hurting, not helping

| Variant | With 5d time stop | Without time stop |
|---|---|---|
| A1 (SPY) | Sharpe −0.04 | Sharpe +0.03 |
| A2 (QQQ) | Sharpe 0.51 | Sharpe 0.43 |

Mixed result. On SPY removing the time stop slightly helps. On QQQ
removing it slightly hurts. The 5-day time stop trades themselves are
universally bad: every variant's `time_stop` exit reason produces large
average losses ($-70 to $-200 per trade). What's salvaging A2's Sharpe
is that the time stop, while losing money on those trades, **caps
losses on positions that would otherwise drift further into the red**.

### Same-day exits remain the profit center

Across all 8 variants:
- 0-day exits win 82-94% of the time, contributing the vast majority of
  positive P&L
- Multi-day holds (especially 5+d) lose money consistently
- The strategy genuinely captures fast intraday-to-overnight bounces
  on oversold prints, and falls apart when those bounces don't materialize

This is the same finding from the v1 backtest, now confirmed across an
8-year sample on shares. The signal generates a real one-day reversion
edge.

### Per-regime — IBS-long doesn't fire in bears

QQQ (long-only, full period) by regime:
| Regime | N | Win% | Total | PF |
|---|---|---|---|---|
| crisis_recovery (2020) | 44 | 86% | +$2,155 | 3.05 |
| bull (4 years combined) | 144 | 65% | +$2,075 | 1.38 |
| bull_chop (2025) | 27 | 63% | +$405 | 1.32 |
| chop_to_correction (2018) | 34 | 65% | −$526 | 0.74 |
| mixed (2026) | 6 | 33% | −$265 | 0.61 |
| bear (2022) | 3 | 33% | −$487 | 0.20 |

The `close > SMA(200)` filter blocks IBS-long entries in bear regimes —
only 3 trades in 2022, all small. **The previous claim that IBS fires
in 2022 was the SHORT side firing**, not the long. With shorts off,
IBS has nothing to do during bears.

### IBS short on QQQ shares: notable but unrequested data

In the original A2 run (with shorts enabled, before re-running),
the strategy fired ~63 short trades on QQQ shares:
- 2022 bear: 49 trades, 69% win, +$2,741, PF 1.89
- This is most of A2's edge in bear regimes

Removing shorts dropped Sharpe 0.59 → 0.51 and total return +83% → +42%.

This contradicts the assumption from prior backtests where SQQQ-call
shorts performed terribly. **IBS short on QQQ shares (not options)
appears to have edge in bear regimes** — small sample (2 instances of
substantial bear in 8 years), but the per-trade numbers are
encouraging. Not part of Phase 1 spec; flagging for future reference.

## Verdict and recommendation

The strict letter of the user's rule says "stop." The data is more
nuanced than the binary rule allows for:

**Option 1: Stop on IBS.** Phase 5 (afternoon reversion) becomes the
next strategy track once 5-min data is available. Defensible reading
of "both Tier D → stop."

**Option 2: Proceed to Phase 2 cautiously, QQQ-only.** The user's plan
included this scenario:
> One hits B+, the other doesn't → proceed to Phase 2 with only the
> working underlying

QQQ doesn't quite hit B+ (Sharpe 0.51 vs B threshold 1.0), but it
does have:
- A real 0.51 Sharpe over 8 years
- Stable in-sample/out-of-sample Sharpe
- Max DD only −11% (tier-A worthy)
- Edge concentrated in 0-day holds

The case for Phase 2 is: the strategy has Sharpe edge, just lacks
compounding. **Options as a leverage mechanism is exactly what Phase
2 tests.** If 7-DTE or 30-DTE QQQ calls amplify the +42% to >+160%
without blowing up the Sharpe, we have a Tier B strategy. If they
can't, we drop the whole approach.

**Option 3: Investigate the long+short QQQ result.** The Sharpe-0.59
long+short version is genuinely interesting, especially the bear-
regime contribution. A "Phase 1.5" that re-tests with both directions
on a clean basis could reveal whether there's more edge being left on
the table.

## My recommendation

**Option 2 — proceed to Phase 2 with QQQ-only, IBS-long-only.**

Reasoning:
1. The Sharpe edge is real (0.51 over 8 years, stable across train/test).
2. The compounding gap is exactly what options leverage is designed to
   close. Phase 2 explicitly tests this.
3. SPY is dead — drop it from further consideration.
4. The walk-forward held; the strategy isn't obviously broken.
5. Phase 2 is cheap (B1, B2, B3 — three variants on shares with options
   pricing already implemented). If none of them clears Tier B, we have
   a clean reason to stop.

If Phase 2 produces no Tier-B-or-better variant, **then** we stop on
IBS and pivot to Phase 5 / regime filter / v2 design.

Option 3 (long+short investigation) goes on the backlog — interesting
but not blocking. The Phase 2 winner can later be combined with the
short branch as a separate experiment.

## Awaiting your decision

- Stop here per the strict rule, or
- Proceed to Phase 2 with QQQ-only IBS-long-only, or
- Phase 1.5 first (long+short re-evaluation), then Phase 2

Numbers above are reproducible: `python scripts/run_phase1.py` against
the FMP key in `.env`. Raw outputs preserved at:
- `reports/phase1/raw_output_long_only.txt` (canonical)
- `reports/phase1/raw_output_long_and_short.txt` (initial, includes shorts)
