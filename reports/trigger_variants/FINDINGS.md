# Test A — Faster-trigger variants

**Date:** 2026-05-03
**Branch:** claude/strategy-validation-v2
**Script:** `scripts/run_trigger_variants.py`
**Raw output:** `output.txt`

## Setup

- **Underlying:** QQQ, 2000-01-03 → 2026-04-15 (26 years)
- **OFF treatment:** T-bill (FRED DGS3MO, daily-compounded)
- **Variants tested:**
  - v1: 50/200 SMA crossover (baseline)
  - v2: 20/100 SMA crossover
  - v3: 50/200 + 10% DD circuit breaker (60-day high)
  - v4: 20/50 SMA crossover
  - v5: 50/200 + 2× ATR(20) drop from 60-day peak
  - v6: 50/200 + VIX > 30 AND 5d-MA > 20d-MA panic detector

- **Locked decision criteria (all 4 must hold):**
  1. Sortino improvement ≥ 0.3 over baseline
  2. After-tax CAGR ≥ baseline
  3. Max DD materially better (≥ 0.5pp)
  4. Transition count ≤ 2× baseline

---

## Headline Result

**No variant wins under both backtest conventions. 50/200 baseline holds.**
The lag is inherent to the strategy.

But this test surfaced a bigger issue with the prior framework. Read on.

---

## Backtest convention disclosure (CRITICAL)

While building this test I noticed our prior framework uses what I'll call
**Convention 1** — `flag[t] → ret[t]`: today's flag (computed from today's
close) determines whether we capture today's return. This is widely used in
public BAH-on-trend backtests and CAN be approximately achieved with MOC
(market-on-close) orders, but it has a subtle look-ahead: to capture
`ret[t] = C(t)/C(t-1) − 1`, you needed to be long from `C(t-1)` to `C(t)`,
but `flag[t]` is observed only at `C(t)`. Real-world MOC fills near-but-not-at
the close, so capturing ret[t] requires having entered at C(t-1).

**Convention 2** — `flag[t-1] → ret[t]`: yesterday's flag determines today's
return (decide at close, fill at close, capture next-day return). This is
the honest no-lookahead convention.

For variants that flip ON/OFF infrequently (slow MAs), the difference is
small. For fast triggers, Convention 1 captures more flip-day returns and
inflates Sortino.

I ran both conventions side by side. The results:

### Convention 1 (lookahead, prior framework)

| Variant | Sortino | CAGR | AT CAGR | |DD| | Trans/yr |
|---|---:|---:|---:|---:|---:|
| v1: 50/200 (baseline) | **3.85** | +28.0% | +26.7% | 11% | 6.28 |
| v2: 20/100 SMA | 6.48 | +40.0% | +38.6% | 6% | 10.27 |
| v3: 50/200 + 10% DD | 3.96 | +28.3% | +27.0% | 7% | 6.36 |
| v4: 20/50 SMA | 5.73 | +38.9% | +37.4% | 7% | 10.12 |
| v5: 50/200 + 2× ATR | 6.27 | +33.9% | +32.5% | 5% | 8.98 |
| v6: 50/200 + VIX panic | 4.09 | +28.4% | +27.1% | 7% | 6.51 |

**Winners under locked criteria:** v2, v4, v5.

### Convention 2 (no-lookahead, honest)

| Variant | Sortino | CAGR | AT CAGR | |DD| | Trans/yr |
|---|---:|---:|---:|---:|---:|
| v1: 50/200 (baseline) | **0.83** | +6.3% | +5.4% | 22% | 6.28 |
| v2: 20/100 SMA | 0.75 | +5.3% | +4.5% | 22% | 10.27 |
| v3: 50/200 + 10% DD | 0.80 | +5.9% | +5.1% | 22% | 6.36 |
| v4: 20/50 SMA | 0.59 | +4.3% | +3.6% | 30% | 10.12 |
| v5: 50/200 + 2× ATR | 0.70 | +4.6% | +3.8% | 22% | 8.98 |
| v6: 50/200 + VIX panic | 0.80 | +5.9% | +5.0% | 22% | 6.51 |

**Winners under locked criteria:** NONE.

### Robust winners (both conventions): NONE

The Convention 1 wins for v2/v4/v5 are entirely driven by the look-ahead
amplification — fast triggers benefit MORE from `flag[t] → ret[t]` than slow
triggers because they react more strongly to today's close. Removing the
lookahead, none of them beat baseline.

---

## Decline-event drawdown avoidance (Convention 2)

| Variant | 2000-2002 | 2008-2009 | March 2020 | 2022 |
|---|---|---|---|---|
| v1: 50/200 baseline | 83→0% (+83) | 44→0% (+44) | 29→9% (+19) | 35→4% (+30) |
| v2: 20/100 SMA | 83→15% (+68) | 44→0% (+44) | 29→7% (+22) | 35→9% (+25) |
| v3: 50/200 + 10% DD | 83→0% (+83) | 44→0% (+44) | 29→9% (+19) | 35→4% (+30) |
| v4: 20/50 SMA | 83→30% (+53) | 44→10% (+34) | 29→7% (+22) | 35→7% (+27) |
| v5: 50/200 + 2× ATR | 83→0% (+83) | 44→0% (+44) | 29→7% (+22) | 35→4% (+30) |
| v6: 50/200 + VIX panic | 83→0% (+83) | 44→0% (+44) | 29→9% (+19) | 35→4% (+30) |

The 50/200 baseline already avoids ~83% of the 2000-2002 dotcom drawdown,
~44% of the 2008-2009 GFC, and ~30% of the 2022 inflation drawdown. The
March 2020 COVID crash is the one event where it's marginally lagging
(catches it at 9%, BAH would be 29%). Faster triggers avoid 2pp more of
March 2020 — but at the cost of producing whipsaw losses in 2000-2002
(15-30% strategy DD vs 0% for the 50/200 baseline).

The data confirms: 50/200 already captures decline avoidance well. Faster
triggers don't earn their whipsaw cost.

---

## Buy-and-hold sanity check (Convention 2)

Does the strategy still beat buy-and-hold on risk-adjusted metrics under
the honest convention? Yes — meaningfully:

| Vehicle | Sortino | CAGR | |DD| | Final $ |
|---|---:|---:|---:|---:|
| QQQ buy-and-hold | 0.58 | +7.5% | **83%** | $53,074 |
| SPY buy-and-hold | 0.57 | +6.1% | 56% | $38,200 |
| **BAH-on-trend (Conv 2)** | **0.83** | +6.3% | **22%** | $39,451 |
| BAH-on-trend (Conv 1) | 3.85 | +28.0% | 11% | $5,281,157 |

**The real edge:** BAH-on-trend Sortino (0.83) is +0.25-0.26 over buy-and-hold.
|DD| is dramatically better (22% vs 83% for QQQ, vs 56% for SPY). Final
equity is ~comparable to SPY BAH. The strategy genuinely reduces drawdown
risk at a small cost in CAGR.

**The Tier A claim was wrong.** Under Convention 1's look-ahead, the strategy
appeared to deliver Sortino 3.85 — far above Tier A's 1.5 floor. Under
Convention 2 the actual achievable Sortino is 0.83. The strategy STILL
beats benchmarks but doesn't clear the Tier A bar that was originally locked.

---

## Decisions

### Test A: confirmed
**50/200 SMA + T-bill OFF holds as the baseline trigger.** No variant wins
under both conventions.

### Framework concern: needs your call
The look-ahead bias affects every backtest in this validation chain. The
relative findings (BAH > LEAPS, T-bill > inverse ETFs, IBS overlay rejected
on Sortino, etc.) likely survive because the bias affects them all similarly.
But the **absolute** Tier A claim doesn't survive.

Three options:
1. **Re-validate everything under Convention 2.** Cleanest but undoes weeks
   of work. Tier A criteria need to be recalibrated (probably Sortino > 0.7
   given BAH baseline of 0.57).
2. **Accept that Convention 1 is the deployment scenario** if you commit to
   MOC discipline (submit orders during the 15:50-15:55 ET window based on
   pre-close SMA reading). The look-ahead becomes a small numerical noise
   rather than a fundamental bias. Accept the prior validation chain.
3. **Disclose both conventions in deployment.** Recommend the strategy with
   the honest expected performance (Conv 2: 6% CAGR, 22% DD, Sortino 0.83
   over buy-and-hold's 0.58). Drop the Tier A framing.

### Test B: recommend pausing
Test B asks "what to hold during OFF periods" — the trigger is fixed at the
Test A winner (50/200). Under Convention 2, OFF periods earn 1.96% T-bill
yield. The space for improvement (1-2pp via TLT/IEF/GLD) is meaningful in
proportion to the 6.3% baseline CAGR.

But before running Test B, I want your call on the framework concern. The
trigger choice doesn't change between Conv 1 and Conv 2 (50/200 baseline holds
both ways), so Test B can proceed with the same trigger. But the question
of "is the strategy actually deployable" needs to be settled first.
