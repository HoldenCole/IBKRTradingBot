# Overnight Drift findings — Priority 3 candidate

**Date:** 2026-05-02
**Period:** 2018-01-01 → 2026-04-15 (8.3 years)
**Mechanic:** Buy at session close T, sell at next session open T+1. Always
long, daily, single position at a time. No signal logic.
**Universe:** SPY and QQQ tested separately.
**Slippage scenarios:** 1 bp each side (realistic MOC/MOO on liquid ETFs)
+ 0 bp (upper-bound diagnostic).

## Key finding

**Overnight drift on QQQ shows the strongest out-of-sample evidence of any
strategy tested so far.** QQQ test slice (2023-2026, 822 trades) under
realistic 1bp slippage produces Sortino **1.14**, Sharpe 0.89, return +39%,
max DD 18% — Tier B Sortino, Tier D return-vs-bench.

## Headline table

| Variant | N | Win% | Sharpe | **Sortino** | Return | |DD| | Final $ |
|---|---|---|---|---|---|---|---|
| SPY full (1bp slip) | 2081 | 54% | 0.28 | 0.31 | +25% | 29% | $9,997 |
| SPY train (2018-22) | 1258 | 54% | 0.20 | 0.22 | +10% | 29% | $8,779 |
| **SPY test (2023-26)** | 822 | 55% | 0.46 | **0.56** | +13% | 17% | $9,052 |
| QQQ full (1bp slip) | 2081 | 54% | 0.47 | **0.55** | +60% | 31% | $12,777 |
| QQQ train (2018-22) | 1258 | 54% | 0.25 | 0.29 | +14% | 29% | $9,116 |
| **QQQ test (2023-26)** | 822 | 55% | 0.89 | **1.14** | +39% | 18% | $11,097 |
| SPY full (NO slip) | 2081 | 56% | 0.68 | 0.74 | +87% | 29% | $14,977 |
| QQQ full (NO slip) | 2081 | 56% | 0.81 | 0.95 | +139% | 27% | $19,159 |
| QQQ test (NO slip) | 822 | 56% | 1.30 | **1.66** | +63% | 17% | $13,011 |

Benchmarks (SPY buy-and-hold): full +160% Sharpe 0.70 Sortino 0.85;
test (2023-26) +84% Sharpe 1.30 Sortino 1.85.

## Critical observations

### 1. Train-vs-test divergence is OPPOSITE of published-edge-weakening narrative

You specifically asked me to look for evidence of edge weakening. The
data shows the opposite — **overnight drift edge has STRENGTHENED in
the test period (2023-2026)**:

| | Train (2018-22) | Test (2023-26) | Δ |
|---|---|---|---|
| SPY Sortino (1bp) | 0.22 | 0.56 | +0.34 |
| QQQ Sortino (1bp) | 0.29 | 1.14 | **+0.85** |
| SPY Sortino (no slip) | 0.59 | 1.19 | +0.60 |
| QQQ Sortino (no slip) | 0.64 | 1.66 | +1.02 |

Every variant shows train < test. Win rates are stable ~54-56% across
both slices, so the improvement comes from the MAGNITUDE of overnight
moves, not the frequency. Likely regime-driven: 2023-2026 had a clean
bull market with limited overnight gap-down events; 2018-2022 included
2020 COVID gap-down and 2022 gap-down days that hurt always-long
overnight strategies.

This means: **deploying overnight drift on the basis of historical
edge would NOT have looked dead heading into 2023**, contrary to some
published narratives. The strategy reasserted itself.

### 2. Slippage is the binding cost

Comparing 0bp vs 1bp slippage:

| | 0bp slip Sortino | 1bp slip Sortino | Drag |
|---|---|---|---|
| SPY full | 0.74 | 0.31 | -0.43 |
| QQQ full | 0.95 | 0.55 | -0.40 |
| QQQ test | 1.66 | 1.14 | -0.52 |

A consistent ~0.4-0.5 Sortino drag from 1bp/side slippage. For 2081
round-trips at 1bp each side = 10 bps of compounded cost per trade
× 2081 trades ≈ 20% gross-to-net drag on equity.

**Live execution quality matters enormously here.** IBKR's MOC/MOO
auctions on SPY/QQQ typically clear within 0.5 bp of close/open
reference. If actual slippage is closer to 0.5 bp/side instead of 1
bp/side, the strategy lifts halfway between the two columns above.
Pre-deployment paper trading should measure actual fill quality before
sizing.

### 3. Absolute returns are realistic but modest

Per your specific ask — don't get distracted by Sharpe/Sortino if
absolute returns are trivial:

| Variant | $8k → over 8 years | Per-year $ |
|---|---|---|
| SPY full (1bp) | $9,997 | +$250 |
| QQQ full (1bp) | $12,777 | +$575 |
| QQQ full (no slip) | $19,159 | +$1,345 |

QQQ overnight at +$575/year on $8k is real money but small. For
multi-strategy framing, where this is one component of a 3-strategy
portfolio, it contributes diversifying edge that's stylistically
uncorrelated with IBS mean reversion. The absolute return contribution
to a portfolio is modest unless levered.

### 4. Drawdown is comparable to buy-and-hold, not better

Max DD on overnight QQQ full is 31% (vs QQQ buy-and-hold 36%). On SPY
full it's 29% (vs SPY 34%). Slight reduction but not a drawdown play.
Test-period DD of 17-18% is much better, but that's a regime artifact
(2023-2026 didn't have a major drawdown event).

### 5. Win rate is consistent across slices

54-57% across all variants, both with and without slippage. This is
a stable feature of the data, consistent with the published 57-60%
overnight win rate for SPY since 2000. The strategy isn't "broken"
in the modern era — it's still firing winners at the historical rate.

## Tier verdicts under v2 rules

| Variant | Sharpe-or-Sortino | Return-vs-bench | DD | Tier |
|---|---|---|---|---|
| QQQ test (1bp) | 1.14 ≥ 1.0 ✓ | +39% vs +84% (fails) | 18% ✓ | D |
| QQQ test (no slip) | 1.66 ≥ 1.0 ✓ | +63% vs +84% (fails) | 17% ✓ | D |
| QQQ full (1bp) | 0.55 ≥ 0.5 ✓ | +60% vs +160% (fails) | 31% ✓ | D |
| All others | varies | mostly fails | varies | D |

**Strict tier rule: every variant is Tier D.** The binding constraint
is always the absolute-return-vs-SPY rule, same as IBS. The Sortino
clears Tier C (and Tier B in some test slices), but the absolute
return doesn't beat the SPY benchmark.

## Honest read for the multi-strategy framing

Per your framing:
> Individual components can clear Tier C and still earn their place
> if they're uncorrelated with the others.

Overnight drift on QQQ (with realistic 1bp slippage):
- Sortino 0.55 full period — passes Tier C Sortino
- Sortino 1.14 out-of-sample — passes Tier B Sortino
- Win rate 54%, stable across regimes
- **Style-uncorrelated with IBS** (no signal, always long, overnight only)
- **Time-horizon-uncorrelated with IBS** (16-hour holds vs multi-day)
- BUT highly correlated with SPY/QQQ buy-and-hold (it IS a market exposure)

This is a viable component candidate. It contributes:
- Stable, mechanical income stream (54% win rate, small per-trade P&L)
- Different risk profile than IBS (no signal-failure regime risk)
- Different operational profile (MOC/MOO orders, no intraday monitoring)

It does NOT contribute:
- Drawdown reduction (DD comparable to buy-and-hold)
- Bear-regime hedge (always long; gets hit on overnight gaps down)
- Significant absolute return at 1x sizing

## Recommendation

**Slot overnight drift on QQQ as Component #2** in the multi-strategy
portfolio framing.

- Component #1: IBS-on-QQQ-shares (long+short), pending regime filter
- Component #2: **Overnight drift on QQQ** (proposed)
- Component #3: TBD (afternoon reversion when intraday data ready, or
  another candidate)

This is a Tier B-Sortino strategy in the test period that pays for
its slot with a stable mechanical edge. Combined with IBS (which has
the opposite problem — high Sortino in some regimes, fails in others),
the portfolio could approach Tier B at the aggregate level.

The train-vs-test divergence in overnight drift is **good news**, not
bad. It means the strategy isn't dead heading into deployment.

## What to confirm before deployment

1. **Live MOC/MOO fill quality on IBKR paper account.** Run 2-4 weeks
   of paper trading; measure actual slippage vs reference. If under
   0.5 bp/side, the strategy is closer to the 0bp upper bound. If
   over 1 bp/side, headline metrics shrink.

2. **Position sizing in a multi-strategy portfolio.** Allocating 100%
   of capital to overnight drift while IBS is also active means
   leverage > 1x. Need a sizing policy (e.g., overnight = 50% of
   capital, IBS = 50%) and engine support for that.

3. **Drawdown coordination.** Both IBS-long and overnight drift are
   long-biased. If both lose simultaneously in a crash, max DD
   compounds. The third component should counterbalance this.

## What's pushed

- `src/backtest/overnight_engine.py` — focused overnight engine
- `scripts/run_overnight.py` — runner with slippage scenarios + walk-forward
- `reports/overnight_drift/FINDINGS.md` (this doc)
- `reports/overnight_drift/raw_output.txt`
- `tests/test_v2_foundation.py` — three new tests (105 total passing)

## Awaiting your call

1. Slot overnight drift as Component #2? (My recommendation: yes)
2. Confirm IBKR puller status — is `data/intraday/` populating? Phase 5 starts when the cache fills.
3. Any adjustments to the overnight scope before next priority?
