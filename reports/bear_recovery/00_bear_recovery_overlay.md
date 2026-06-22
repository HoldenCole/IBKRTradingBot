# Bear-Recovery Dynamic Allocation Overlay — Test Result

**Date:** 2026-06-22
**Runner:** `scripts/run_bear_recovery_overlay.py`
**Raw output:** `RESULTS_bear_recovery.txt`
**Verdict:** **TIER D** under the locked criteria. The strategy
fails on Sortino improvement; it does NOT fail on cycle dominance.

## The honest headline

Sortino improvement over the static 50/50 baseline:

| Variant | CAGR | Sortino | Δ Sortino | MaxDD | Cycles+ | Dominance | Tier |
|---|---:|---:|---:|---:|---:|---:|:--:|
| **Primary (70/30, 100%, 250%)** | **+45.1%** | **2.40** | **+0.07** | 28% | 25/60 | 29% | **D** |
| Initial 60/40 | +40.6% | 2.43 | +0.10 | 25% | 24/60 | 38% | D |
| Initial 80/20 | +49.5% | 2.37 | +0.04 | 31% | 24/60 | 26% | D |
| Rot1 50% | +44.5% | 2.60 | **+0.27** | 24% | 25/60 | 24% | **B** (single) |
| Rot1 150% | +46.1% | 2.38 | +0.06 | 29% | 25/60 | 32% | D |
| Rot2 200% | +44.1% | 2.36 | +0.03 | 28% | 25/60 | 25% | D |
| Rot2 300% | +45.4% | 2.39 | +0.07 | 28% | 25/60 | 28% | D |

Baseline static 50/50 (with trend filters + T-bill OFF): CAGR +36.3%,
Sortino 2.33, MaxDD 23%.

**Six of seven variants land in Tier D directly.** The primary parameter
set produces only +0.07 Sortino improvement — within noise.

## The trigger-count problem (worth flagging upfront)

The user spec assumed "4 major bear-recovery cycles (2015, 2018, 2020,
2022)." The 30-day-both-off rule on actual data fires **60 times**, not 4.
QQQ has many brief (~30-90 day) OFF periods that coincide with BTC
weakness; each triggers a "cycle" by the locked definition. Most of these
are tiny micro-cycles (peak BTC appreciation <10%) that resolve before
any rotation threshold is hit.

The truly "major" cycles by peak BTC appreciation are only 4:

| Trigger date | Trigger BTC | Peak appreciation | Reached rot1? | Reached rot2? |
|---|---:|---:|:--:|:--:|
| 2017-04-04 | $1,144 | +159% | yes | no |
| **2017-09-28** | **$4,201** | **+364%** | **yes** | **yes** |
| 2019-04-25 | $5,465 | +138% | yes | no |
| **2020-10-09** | **$10,916** | **+482%** | **yes** | **yes** |

The 2018 and 2022 "cycles" the user expected don't appear as deep
recoveries in the data — those BTC bottoms didn't satisfy the
30-day-both-off precondition (QQQ wasn't simultaneously OFF for long
enough), or they triggered earlier without the deep multi-month
preconditions assumed.

## Per-cycle attribution for the primary (the real test)

The strategy IS slightly better than baseline on the big cycles:

| Trigger | Peak BTC | Dynamic ret | Baseline ret | Δ |
|---|---:|---:|---:|---:|
| 2017-04-04 | +159% | +74% | +53% | **+22pp** |
| **2017-09-28** | **+364%** | **+142%** | **+99%** | **+43pp** |
| 2019-04-25 | +138% | +58% | +35% | **+23pp** |
| **2020-10-09** | **+482%** | **+158%** | **+142%** | **+16pp** |

Sum of outperformance on the 4 major cycles: **+104pp**. Sum of positive
outperformance across all 60 cycles: ~151pp. Sum across all cycles
(including negatives): ~+85pp. So the big 4 cycles ARE responsible for
most of the strategy's added value — but the dominance check (locked at
"any single cycle >50% of total outperformance") doesn't flag it because
the value is spread across 4 cycles, not concentrated in 1.

**Why the strategy still fails Tier B despite this:** the Sortino number
doesn't move enough. CAGR rises from 36% to 45% (a meaningful 9pp), but
volatility also rises (BTC-heavy weighting means more downside variance
on the BTC sleeve), so Sortino barely changes. Risk-adjusted, the
strategy isn't a meaningful improvement.

## The one passing variant (rot1 50%) — investigate

The "rotate at 50% appreciation instead of 100%" variant lands Tier B
(Sortino improvement +0.27). But this is **interpretable, not a winner**:

- 50% is half of the primary's 100% threshold. The earlier rotation moves
  the strategy toward the baseline 50/50 sooner, reducing the BTC-heavy
  exposure during the volatile mid-cycle. **It works because it makes the
  strategy more like the baseline.**
- The neighbors fail (rot1 150% = Tier D, indicating the result is
  sensitive to the specific threshold).
- Per the overfit-downgrade rule, even if rot1 50% were the primary, the
  Tier B downgrades to C because neighbors fail.

The honest read: "earlier rotation" doesn't validate the strategy
mechanism; it validates that being closer to 50/50 is closer to optimal.
That's an argument against the dynamic-allocation thesis, not for it.

## What does work in the data (mechanistically)

Per-cycle BTC appreciation is highly variable: most cycles are duds (no
rotation triggered), 4 are spectacular (>100% peak), 1 is parabolic
(+482%). The strategy's mechanism — be heavy in BTC at the start, rotate
to QQQ as BTC matures — works IF you're in one of the 4 spectacular
cycles. But you can't tell ex-ante which cycle is going to be
spectacular. The trigger fires the same way for a +5% cycle as for a
+482% cycle.

The strategy effectively says "every bear recovery, go BTC-heavy."
Half the time (30 of 60 cycles) BTC barely moves and the heavy
allocation doesn't help. The dilution kills the Sortino improvement
that the big cycles produce.

## Operational metrics (primary)

- 60 cycles detected in ~12 years = ~5 per year
- Avg weight rotations: 10.2 per year (each cycle has trigger + potential
  rot1 + potential rot2 + cycle-end reset; most cycles only hit trigger
  + reset = 2 rotations)
- Each rotation = 2 taxable events (reweight both sleeves)
- Estimated annual tax drag from rotations: ~0.5-1% (small, not killing)

Cost isn't the binding constraint. The strategy's edge just isn't large
enough to justify the complexity.

## What about the "worst-case rotation" question

The user asked to identify rotations where forward outcome was bad
(rotated to QQQ then BTC kept running, or rotated and market crashed).

The closest case is **2020-10 cycle**: hit rot2 at +250% BTC appreciation
(BTC ~$38k), then BTC kept running to +482% peak (~$63k). At rot2 weight
(30% BTC vs initial 70% BTC), the strategy "missed" ~25pp of the BTC leg
on that segment. But the rotated-to-QQQ allocation captured ~7pp from
QQQ rallying alongside. Net "missed" ≈ 18pp on the BTC sleeve during the
final leg of that run.

That said, the full cycle still outperformed baseline by 16pp, so the
rotation didn't kill the cycle's edge — it just constrained it.

In a real-time setting, this is the rotation that would feel worst:
sitting at 30% BTC while BTC runs to a fresh peak. The trade-off is
philosophical: if you ALWAYS rotate at +250%, you cap the upside on the
biggest runs. If you NEVER rotate, you sit in BTC-heavy through inevitable
drawdowns. The data says the cost of rotating exceeds the benefit on
average.

## What this confirms

**Static 50/50 with independent trend filters is the right baseline.**
The user pre-stated this and the test confirms it. The dynamic overlay's
mechanism is reasonable in theory (BTC has asymmetric recovery upside)
but the implementation:

1. Triggers too often (60 cycles, not 4) because the 30-day-both-off
   precondition is satisfied frequently in chop, not only in major bears
2. Can't distinguish ex-ante between a +5% cycle and a +500% cycle
3. The BTC-heavy initial allocation amplifies losses in the dud cycles
   roughly as much as it amplifies gains in the spectacular cycles
4. Net Sortino improvement is +0.07 — noise

## Honest framing for deployment

Per the user's framing rule: *"Even if it passes Tier B, recommend
deployment with smaller initial allocation than backtest suggests."*

The test failed Tier B, so this framing doesn't kick in. **No deployment
change.** Static 50/50 stays as the deployed allocation. The bear-recovery
overlay is not deployed.

## Final tier (with the locked checks applied)

| Check | Result |
|---|---|
| Primary Sortino improvement ≥0.30 (Tier A) | ✗ (only +0.07) |
| Primary Sortino improvement ≥0.15 (Tier B) | ✗ (only +0.07) |
| Primary Sortino improvement ≥0.10 (Tier C) | ✗ (only +0.07) |
| Cycle dominance check | ✓ pass (no single cycle dominates at 29%) |
| Cycles working count | 25 of 60 (42%) |

**>>> FINAL TIER: D <<<**

The dominance check (the locked criterion that this test was specifically
designed to enforce) was *passed* — outperformance was spread across the
4 major cycles, not concentrated in 2020-2021. But that doesn't matter
because the strategy fails the Sortino threshold by a wide margin.

## Status

This is the last research item per the user's spec. Result: Tier D, no
deployment change. The deployed portfolio is the static 50/50 (QQQ trend
+ BTC trend, each with independent trend filters and T-bill OFF
treatment) at the locked account-size-conditional vehicles.

**Research phase FINAL CLOSED.** Move to operational deployment.
