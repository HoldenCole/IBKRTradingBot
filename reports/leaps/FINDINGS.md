# LEAPS — both tests FAIL, eliminated as deployment vehicle

**Date:** 2026-05-02 / 2026-05-03
**Strategy:** Same SMA(50)/(200) BAH-on-trend rule, executed via SPY LEAPS calls.
**Test 1:** 0.80 delta, 18mo tenor, 60% sizing, roll at 6mo remaining.
**Test 2:** 0.70 delta, 12mo tenor, 80% sizing, roll at 4mo remaining.
**Backtest:** 2000-2026 yfinance SPY + FRED VIX. Three periods.

## Decision rule — both tests FAIL

| | Test 1 (0.80Δ/18mo/60%) | Test 2 (0.70Δ/12mo/80%) |
|---|---|---|
| Sortino in-sample | **1.73** | **1.91** |
| Sortino gate (≥0.80×3.89=3.11) | **FAIL** | **FAIL** |
| Max DD in-sample | −24.5% | **−39.4%** |
| Max DD gate (<25%) | PASS | **FAIL** |
| After-tax CAGR vs shares+5pp | 14.3% vs 23.5% — **FAIL** | 29.2% vs 23.5% — PASS |
| vs futures 1.5x | LOWER | LOWER |

Test 1 fails on Sortino and CAGR. Test 2 fails on Sortino and DD. Both
underperform futures 1.5x on after-tax CAGR. Per locked discipline:
**no Test 3, no parameter tuning. LEAPS is off the table for this strategy.**

## After-tax CAGR comparison (lower bracket, all three periods)

| Period | Shares 1x | Futures 1.5x | LEAPS T1 | LEAPS T2 |
|---|---|---|---|---|
| 2018-2026 | +18.5% | **+30.7%** | +14.3% | +29.2% |
| 2010-2017 | +18.1% | **+30.1%** | +5.7% | +14.8% |
| 2000-2009 | +11.1% | **+18.2%** | +1.7% | +4.0% |

LEAPS underperforms shares in 5 of 6 cells (Test 2 in-sample is the only
win, and it's still below futures 1.5x). Held-out periods are catastrophic.

## The structural reason — and it's a big one

**LEAPS need long holding periods to capture their tax advantage. The
BAH-on-trend rule has very short effective holding periods.**

Key operational stats from the backtest:

| Metric | Test 1 (in-sample) | Test 1 (full 26yr) |
|---|---|---|
| Trades closed | 46 | 158 |
| Rolls | 0 | 0 |
| Filter-off exits | 45 | 155 |
| **Avg hold (days)** | **34** | **29** |
| **LTCG qualified (>365d)** | **0 of 46 (0%)** | **0 of 158 (0%)** |

The filter flips frequently — many short ON regimes interspersed with OFF
regimes, especially during chop / corrections. Average ON-regime length is
under 35 calendar days, and **zero LEAPS positions across 26 years held
long enough to qualify for LTCG treatment**.

So the ONE thing LEAPS was supposed to give us — favorable LTCG taxation
on long-held positions — never materializes for this strategy. Every exit
is short-term, taxed at 24-37% federal (no NIIT modeled), exactly the same
as shares.

## Why LEAPS lose money when filter flips frequently

Each cycle costs:
- **Spread on entry** (~1% of premium) — paid every cycle
- **Spread on exit** (~1% of premium) — paid every cycle
- **Theta accumulation** during hold — small for LEAPS (~$0.02/day on
  $50 option = 4 bps/day) but adds up over 30-day average hold
- **IV crush risk** — if VIX is high at entry and falls during hold, the
  vega component of P&L is negative

For Test 2 (aggressive, 0.70 delta): leverage on the move IS captured in
the option's delta, so when SPY rallies the LEAPS rallies more in absolute
terms. But the cost stack on each filter cycle eats most of the lift.

For Test 1 (conservative, 0.80 delta): the option behaves more like
leveraged stock (deeper ITM = closer to delta 1). Less convex upside.
Same costs. Net result: lower returns than even un-leveraged shares.

## Why drawdowns are large

Test 2 2018-2026 max drawdown −39.4%. Mechanism: a big LEAPS position
opened near a regime peak, then filter flips during a sharp pullback,
gets sold at materially lower price than entry. Each such cycle compounds
the damage.

Test 1 has lower DD (−24.5%) because the deeper-ITM call is less convex,
so less premium destruction on adverse moves. But it also gives up upside.

## Three things this rules out

1. **LEAPS as the BAH-on-trend deployment vehicle.** Eliminated cleanly.
   Better risk-adjusted, better return, simpler operationally to use
   shares or futures.

2. **The "LTCG via LEAPS" tax-arbitrage thesis for this rule.** Avg hold
   is too short. The strategy is structurally wrong for LEAPS.

3. **Test 3 (calendar variant) — not run.** Both Test 1 and Test 2 failed
   decisively, not borderline. Per locked discipline: no further LEAPS
   parameter exploration.

## What this DOESN'T rule out

LEAPS as a vehicle for **different** strategies that DO have long natural
holding periods. Examples:
- Always-long-LEAPS-on-QQQ (no filter, just always own deep-ITM calls,
  rolled annually). Hold = full year minimum. LTCG-qualified.
- LEAPS on slow signals (e.g., yearly rebalancing, multi-year trend).
  Hold periods ≫ 1 year. LTCG-qualified.
- LEAPS as portfolio insurance (deep-OTM puts, held through expiration).
  Different mechanic entirely.

These are different strategies, not BAH-on-trend variants.

## Operational notes (would-be useful if LEAPS had won)

For each test:
- **Cycles per year (in-sample 2018-2026):** ~5.5 entries/exits annually
  (46 closed trades / 8.3 years). Operationally: ~5x/year manual or
  automated trading.
- **Days in position:** 76% of trading days. The strategy is "in" the
  market most of the time but the IN sessions are short.
- **Worst single-position loss (Test 2):** −$6,759 (84% of starting
  capital wiped on a single bad cycle). Operationally: this is a real
  drawdown event the operator would observe.

## Updated deployment recommendation (unchanged)

The previous decision stands:
- **Phase 1 ($8k):** QQQ or SPY shares with SMA(50)/(200) gate.
- **Phase 2 ($15-20k):** migrate to 1 MES at ~2x leverage.
- **Phase 3 ($50k+):** add MNQ; multi-strategy book becomes viable.

LEAPS not on the path.

## Methodology caveats

1. **VIX as IV proxy.** Real LEAPS IV is term-structure-dependent. I used
   VIX × 1.05 (Test 2, 12mo) and VIX × 1.08 (Test 1, 18mo) which slightly
   overstate IV — penalizes LEAPS in the backtest. If true LEAPS IV is
   below VIX (term structure inversion in stress), my numbers underestimate
   LEAPS performance modestly. Doesn't change the eliminate-decision —
   gap is too large.

2. **Spread modeled at 2% of mid.** Live SPY LEAPS at the deltas tested
   trade ~1-3% spread. Real-world execution likely similar.

3. **Skew assumed flat across 0.70-0.80 delta range.** Reasonable for
   slightly-ITM SPX calls; adds maybe ±1 vol point of error per side.

4. **Constant 4% risk-free rate.** Actual rates varied 0-5.5% across
   2000-2026. Time-varying rates would marginally affect LEAPS pricing
   but not the decision.

5. **Fractional contracts allowed in backtest.** At $8k, neither test
   fits whole-contract on SPY. Real deployment would need IWM (cheaper
   premium) or ~$15k+ account.

6. **No early exercise modeling.** SPY pays dividends; deep-ITM long calls
   are rarely early-exercised in practice but can be near ex-div dates.
   Modeling error is small for the holding periods observed.

## Files

- `src/backtest/leaps_engine.py` — engine (preserved for future use)
- `src/backtest/options.py` — extended with delta + dividend yield + 
  strike-from-delta solver (reusable)
- `scripts/run_leaps.py` — runner (preserved)
- `reports/leaps/raw_output.txt` — full output

The pricer extensions are useful infrastructure regardless of the LEAPS
verdict — any future option-strategy test can use them.
