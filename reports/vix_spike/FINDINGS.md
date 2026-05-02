# VIX spike fade — FAILED diversifier criteria, dropped

**Date:** 2026-05-02
**Variants tested:** v0 threshold (VIX > 25 + 5d-mult), v1 spike-rate
(one-day VIX +20%), v2 SPX-down + VIX-up combo.
**Period:** 2018-2026 full + 2018-22 train / 2023-26 test slices.

## Summary table

| Variant | N | Win% | Sortino | Return | Corr | DD $ | Verdict |
|---|---|---|---|---|---|---|---|
| v0_threshold full | 42 | 33% | −0.14 | **−70%** | −0.40 | +$6,619 | FAIL |
| v0_threshold train | 32 | 38% | 0.02 | −25% | −0.42 | +$9,061 | FAIL |
| v0_threshold test | 10 | 20% | −0.28 | −61% | −0.34 | −$3,021 | FAIL |
| v1_spike_rate full | 52 | 33% | −0.10 | **−58%** | −0.28 | +$7,009 | FAIL |
| v1_spike_rate train | 40 | 35% | −0.04 | −28% | −0.32 | +$7,030 | FAIL |
| v1_spike_rate test | 12 | 25% | −0.15 | −41% | −0.19 | −$29 | FAIL |
| v2_spx_down full | 56 | 32% | −0.33 | **−85%** | −0.39 | −$3,708 | FAIL |
| v2_spx_down train | 48 | 33% | −0.33 | −66% | −0.45 | −$2,443 | FAIL |
| v2_spx_down test | 8 | 25% | −0.28 | −55% | −0.21 | −$3,467 | FAIL |

## Diagnosis — the VXX structural bleed

**Correlation is good** (−0.19 to −0.45 across all variants) — long
VXX is genuinely uncorrelated/inversely-correlated with QQQ BAH. That
criterion passes.

**Drawdown hedge is unreliable.** Train period (2018-22, includes the
COVID crash) shows POSITIVE drawdown-period P&L on v0 and v1 (+$7-9k).
Test period (2023-26, no major crashes) shows NEGATIVE drawdown P&L.
The strategy hedges when there's a real crash to hedge against, but
otherwise buys volatility that fizzles.

**Sortino and absolute return fail catastrophically.** All variants
are net loss-makers. Mechanism: VXX has structural negative carry of
~30-50%/year due to contango in VIX futures. Even when entries are
correctly-timed (33% win rate is decent for tail-hedge strategies),
the carry between trades destroys equity.

**Trade count borderline-low** in test slices (8-12 trades) due to
2023-26 being a low-vol regime. Train slices have enough samples.

## Why this strategy as written doesn't work

The three signal variants test different VIX-spike triggers but all
buy VXX shares as the implementation. VXX's structural bleed is the
binding constraint, not the signal quality.

Variants that might work but require different infrastructure:

1. **SVXY short** — mathematically equivalent to long VXX but inverse.
   Carry works in your favor instead of against. Risk: short ETFs blow
   up catastrophically (Feb 2018 volmageddon vaporized inverse vol funds).
   Position sizing must be tiny.
2. **VIX call options** — defined risk, no carry on the option. But
   options pricing depends on IV-of-VIX (vvix), which is its own
   complex regime. Premium can be expensive after spikes.
3. **VIX futures direct** — no carry on individual contracts but
   needs futures account, more capital, and roll mechanics.
4. **SPX put spreads** — the systematic version of "buy put protection
   when vol picks up." Defined risk, no decay during quiet periods.

Each of those is a different strategy, not a parameter tweak of this
one. For the multi-strategy framing, none of them are a quick win.

## What this changes upstream

We now have **zero passing diversifier candidates** in the v2 work:

- IBS-LS on shares: long-bias mean reversion. Tier D.
- Overnight drift: long-bias time-of-day. Negative lift vs BAH.
- VIX spike fade (3 variants): long vol via VXX. Negative Sortino.

The portfolio thesis required at least one diversifier component. None
exists yet. Phase 5 (afternoon reversion) is unlikely to fill this slot
either — it's another long-biased mean-reversion candidate by design.

Genuinely diversifying strategies that haven't been tested:

- Defensive rotation (gold, bonds, dollar) on macro signals
- Trend continuation / breakout (different style, not necessarily
  different correlation)
- Pairs trading on sector ETFs (market-neutral)
- Calendar-anchored strategies (post-FOMC drift, end-of-month rebalance)

These are scoping work for after Phase 5 / regime model land.

## Status

- All three v0/v1/v2 variants: dropped.
- Code preserved at `src/backtest/vix_spike_engine.py` for potential
  future reuse if a non-VXX implementation emerges.
- FRED data integration (`src/data/fred.py`) is reusable for any
  future macro-signal strategy.

## Files

- `src/backtest/vix_spike_engine.py` — engine, three variants
- `src/data/fred.py` — FRED CSV API client (reusable)
- `scripts/run_vix_spike.py` — backtest runner
- `reports/vix_spike/raw_output.txt` — full variant output
