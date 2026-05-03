# Test B — OFF-period parking vehicles

**Date:** 2026-05-03
**Branch:** claude/strategy-validation-v2
**Script:** `scripts/run_parking_vehicles.py`
**Raw output:** `output.txt`

## Setup

- **Trigger:** 50/200 SMA (Test A confirmed baseline)
- **Underlying:** QQQ, 2000-01-03 → 2026-04-15 (26 years)
- **Vehicles tested:**
  - BIL (T-bill, baseline)
  - IEF (7-10yr Treasuries) — moderate duration
  - TLT (20+yr Treasuries) — strongest historical equity diversifier; 2022 risk
  - GLD (gold) — alternative store of value
  - Trend-of-trends overlay — apply 50/200 SMA to {IEF, TLT, GLD}; hold first
    in uptrend; default to T-bill; rebalance every 5 trading days (weekly)

- **Both conventions reported.** Convention 2 (no-lookahead) is the honest
  measure; Convention 1 (lookahead, MOC) is the prior-framework view.

- **Locked decision criteria (all must hold):**
  1. OFF-period CAGR ≥ T-bill + 1pp (1.5pp for trend-of-trends overlay
     given operational complexity)
  2. Total max DD doesn't materially worsen
  3. 2022 OFF-period drawdown ≤ 10% on the parking vehicle alone

---

## Headline Result

**T-bill baseline holds. No parking vehicle wins under Convention 2.**

Reason in one sentence: the only candidate that survives 2022 is the
trend-of-trends overlay (6.6% DD vs 31% for TLT, 21% for GLD, 17% for IEF),
but its OFF-period CAGR contribution is only +0.3pp over T-bill — well
below the 1.5pp bar.

---

## Convention 1 (lookahead, prior framework)

| Vehicle | Sortino | CAGR | |DD| | OFF-CAGR | Final $ |
|---|---:|---:|---:|---:|---:|
| BIL (T-bill, baseline) | **3.85** | +28.0% | 11% | +2.2% | $5.28M |
| IEF (7-10yr Tres) | 3.57 | +29.1% | 20% | +4.0% | $6.64M |
| TLT (20+yr Tres) | 2.95 | +31.2% | 37% | +7.3% | $9.97M |
| GLD (gold) | 2.49 | +29.2% | 29% | +4.2% | $6.75M |
| Trend-of-trends | 3.35 | +29.5% | 19% | +4.6% | $7.13M |

Even with lookahead, TLT/GLD/IEF degrade Sortino while adding CAGR. T-bill
remains best on Sortino under Convention 1.

## Convention 2 (no-lookahead, honest)

| Vehicle | Sortino | CAGR | |DD| | OFF-CAGR | Final $ |
|---|---:|---:|---:|---:|---:|
| BIL (T-bill, baseline) | **0.83** | +6.3% | 22% | +2.2% | $39,451 |
| IEF (7-10yr Tres) | 0.73 | +5.8% | 26% | +1.3% | $34,920 |
| TLT (20+yr Tres) | 0.60 | +5.4% | 42% | +0.6% | $32,046 |
| GLD (gold) | 0.72 | +7.3% | **42%** | +4.3% | $51,469 |
| Trend-of-trends | 0.76 | +6.4% | 40% | +2.5% | $40,779 |

GLD has the highest CAGR but at 42% drawdown. T-bill baseline has the
best Sortino and lowest |DD|.

---

## Equity-bear regime stress test (parking-vehicle-only return / |DD|)

This isolates the parking vehicle's own behavior during equity bear windows
(assume 100% allocation to the vehicle for the window).

| Vehicle | 2000-2002 | 2008-2009 | March 2020 | 2022 |
|---|---|---|---|---|
| BIL | +9.7% / 0.0% | +0.2% / 0.0% | +0.1% / 0.0% | +1.2% / 0.0% |
| IEF | +7.0% / 1.5% | +5.5% / 6.5% | +6.5% / 4.7% | **-16.8% / 17.0%** |
| TLT | +10.6% / 2.0% | +9.8% / 16.7% | +14.3% / 15.7% | **-31.1% / 31.1%** |
| GLD | +0.0% / 0.0% | +14.4% / 22.1% | +2.8% / 12.5% | **-8.0% / 21.0%** |
| Trend-of-trends | +0.0% / 0.0% | -3.0% / 9.0% | +6.5% / 4.7% | **+5.1% / 6.6%** |

The 2022 inflation regime is the killer: it's the only window in 26 years
where bonds AND gold AND equities all sold off simultaneously. TLT lost
31%, IEF 17%, GLD 8%. T-bill earned 1.2% with zero drawdown. Trend-of-trends
caught it (rotated to T-bill before TLT/IEF cratered).

---

## Locked decision evaluation (Convention 2)

| Vehicle | ΔOFF-CAGR | ΔTotal DD | 2022 |DD| | Bar | Pass? |
|---|---:|---:|---:|---|---|
| IEF | -0.9pp ✗ | +3.6pp ✗ | 17.0% ✗ | +1pp | fail |
| TLT | -1.6pp ✗ | +19.5pp ✗ | 31.1% ✗ | +1pp | fail |
| GLD | +2.1pp ✓ | +20.4pp ✗ | 21.0% ✗ | +1pp | fail |
| Trend-of-trends | +0.3pp ✗ | +17.6pp ✗ | 6.6% ✓ | +1.5pp | fail |

**No vehicle wins.** T-bill baseline holds.

---

## Why parking vehicles fail

1. **Bonds (IEF/TLT) are not equity diversifiers in inflation regimes.**
   The 2022 episode is the existential risk. We had 26 years of data and
   only one such regime, but it produced a 31% loss on TLT — large enough
   to dominate the entire OFF-period return contribution and turn the
   total strategy DD from 22% into 42%.

2. **Gold is also a 2022 victim** (-8%) plus has high baseline volatility
   (DD even in non-2022 periods). Its CAGR contribution (+2.1pp under
   Convention 2) is real but doesn't compensate for the +20pp DD.

3. **Trend-of-trends is the smartest of the lot** but the 50/200 SMA
   on bonds/gold rarely fires in uptrend during OFF periods. When QQQ
   is in OFF regime, bonds and gold have often ALSO entered their own
   downtrends or are flat. The overlay defaults to T-bill ~70% of OFF
   days, so its incremental return over T-bill is small.

4. **Operational complexity isn't free.** Trend-of-trends requires monitoring
   3 additional ETFs, weekly rebalancing, multi-asset trend computation.
   For +0.3pp annual OFF-period return, that complexity isn't justified.

---

## Final deployment spec

After Tests A and B:

```
Long instrument:    QQQ shares (1x leverage)
Trigger:            SMA(50) > SMA(200) AND close > SMA(50)
                    Daily-close decision
ON treatment:       100% QQQ
OFF treatment:      100% T-bill (via SGOV or USFR ETF, or SHV)
Initial capital:    $8,000 (Texas-resident taxable account)
```

**Honest expected performance (Convention 2, no-lookahead):**
- CAGR: +6.3% (after-tax: +5.4% at 24% STCG)
- |DD|: 22%
- Sortino: 0.83 (vs QQQ-BAH 0.58, SPY-BAH 0.57)
- Real edge: -61pp |DD| compared to QQQ-BAH at -1.2pp CAGR cost

**Optimistic expected performance (Convention 1, MOC discipline):**
- CAGR: +28.0% (after-tax: +26.7%)
- |DD|: 11%
- Sortino: 3.85
- Requires submitting orders during 15:50-15:55 ET MOC window based on
  pre-close SMA reading.

The actual deployment performance will fall between the two. With
disciplined MOC execution it can approach Convention 1; with EOD-then-
next-open execution it tracks Convention 2.

**Migration to /MNQ futures at $25k+** remains valid (Section 1256 tax
treatment, 1.5x leverage feasible at 2 contracts on $25k notional).
T-bill OFF treatment unchanged.

---

## Conclusion of validation chain

Tests A and B both produced negative results — confirming that the
existing deployment spec (50/200 SMA + T-bill OFF) is essentially
optimal in the explored space. Two clean negatives is meaningful:
the strategy isn't fragile to obvious tweaks.

**Validation chain complete. Deployment spec is locked.**

The remaining open question is the framework (Convention 1 vs 2) — but
Test A and Test B both confirm the SAME deployment regardless of
convention. The trigger and parking choices are robust. Only the
*expected magnitude* of returns differs between conventions.
