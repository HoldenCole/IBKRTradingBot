# Leverage + tax + deployment — final BAH-on-trend recommendation

**Date:** 2026-05-02
**Account:** $8,000 taxable brokerage in Texas (no state tax, federal only)
**Strategy:** BAH-on-trend (hold index when SMA(50) > SMA(200) AND close > SMA(50);
cash otherwise). Tested across 2018-2026 / 2010-2017 / 2000-2009.

## Headline result

The rule's edge is in the SIGNAL, not the leverage. Sortino is essentially
identical at every leverage level (3.83 / 3.82 / 3.82 / 3.82 across 1x / 1.5x /
2.0x / actual-deployable-x). What changes is the ABSOLUTE return AND the
drawdown — both scale linearly with leverage. The strategy doesn't get
"better" with leverage, it gets bigger.

## After-tax CAGR comparison — lower bracket (24% STCG, 15% LTCG)

NDX/MNQ:

| Period | Shares 1x | Futures 1.5x | Futures 2.0x | Futures 5.0x (1 MNQ) |
|---|---|---|---|---|
| 2018-2026 | +28.6% | +47.9% | +68.5% | **+242%** |
| 2010-2017 | +23.2% | +38.7% | +55.1% | **+191%** |
| 2000-2009 | +17.2% | +28.3% | +39.4% | **+118%** |

SPX/MES:

| Period | Shares 1x | Futures 1.5x | Futures 2.0x | Futures 3.6x (1 MES) |
|---|---|---|---|---|
| 2018-2026 | +18.5% | +30.7% | +43.3% | **+90.6%** |
| 2010-2017 | +18.1% | +30.1% | +42.5% | **+89.6%** |
| 2000-2009 | +11.1% | +18.2% | +25.2% | **+49.9%** |

## The deployment reality at $8k

| Target leverage | MNQ feasible? | MES feasible? |
|---|---|---|
| 1.5x | NO — 1 MNQ = 5x, 0 contracts = 0x | NO — 1 MES = 3.6x, 0 contracts = 0x |
| 2.0x | NO | NO |
| Whole-contract minimum | **5x** (1 MNQ on $8k) | **3.6x** (1 MES on $8k) |

The user's stated 1.5x and 2.0x targets are **mathematically optimal**
(same Sortino, manageable drawdowns) but **not deployable at $8k** because
neither MNQ nor MES has a sub-contract option. The closest whole-contract
realities are 3.6x (MES) or 5x (MNQ).

When does leverage targeting become feasible?
- For **MES 2.0x**: account needs ~$15k (1 MES = 2x leverage there)
- For **MES 1.5x**: account needs ~$20k
- For **MNQ 2.0x**: account needs ~$20k (1 MNQ = 2x leverage there)
- For **MNQ 1.5x**: account needs ~$26k

## Drawdown & margin call risk at deployable leverage levels

| Vehicle | DD in-sample (2018-26) | Initial margin | Buffer at $8k start | Margin-call trigger |
|---|---|---|---|---|
| Shares 1x | −10.9% | n/a | n/a | none (no margin) |
| Futures 1.5x (theoretical) | −16.1% | ~$3,300 | ~$4,700 | **~32% index drop** |
| Futures 2.0x (theoretical) | −21.0% | ~$4,400 | ~$3,600 | ~22% index drop |
| **1 MES (3.6x actual)** | **−23.7%** | **$1,500** | **$6,500** | **~22% SPX drop** |
| **1 MNQ (5x actual)** | **−47.3%** | **$2,200** | **$5,800** | **~16% NDX drop** |

A 16% NDX drop has happened multiple times in the 26-year sample
(COVID 2020 had several 10-12% daily drops, and a cumulative 30%
peak-to-trough; 2022 had multiple 5-8% drops). 1 MNQ on $8k would
have margin-called in March 2020 and possibly twice in 2022.

A 22% SPX drop has happened once cleanly (1987) plus accumulated in
2008. 1 MES on $8k is closer to survivable but still tail-risky.

The backtest doesn't model margin calls — it lets the equity ride
through any drawdown. Live deployment doesn't have that luxury.
**The "+242% CAGR" and "+90.6% CAGR" headlines are not reachable
in real life on $8k** because broker would force-liquidate during
the drawdowns that make those numbers possible.

## Operational complexity surface

What futures deployment requires that shares don't:

1. **Quarterly rolls.** Active position must roll to next contract every ~3
   months. CME's standard cycle is March/June/Sept/Dec. Each roll is
   mechanical (close current, open next) but requires monitoring or an
   automated rolling rule. Cost: ~2 bps per roll × 4/yr = 8 bps/yr drag.
   MODELED in backtest.

2. **Daily mark-to-market settlement.** Unlike shares (P&L paper-only
   until you sell), futures P&L is REALIZED every day end. Account
   equity moves daily with the position; cash gets debited/credited
   from a settlement account. Implication: drawdowns hit cash account
   immediately — no "I'll wait for it to come back" without active
   management.

3. **Margin requirements vary with volatility.** CME raises initial
   margin requirements during high-vol regimes. In March 2020, MNQ
   margin spiked from ~$1,800 to ~$3,200 in days. A 1.5x-target sizing
   could become 0.8x effective if margin doubles — and you'd need to
   reduce contracts. NOT modeled in backtest. Real risk.

4. **Section 1256 year-end mark-to-market for taxes.** Even unrealized
   P&L on Dec 31 is treated as realized for tax purposes. If you have
   $50k unrealized gain in MNQ on Dec 31, you owe tax in April even
   though you haven't closed. Cash flow impact, not return impact.
   Plan for it. NOTED, not modeled.

5. **Margin call risk.** Backtest has no force-liquidation. In real
   deployment at 5x leverage on a small account, a fast move could
   liquidate before the trader can react. The leveraged returns above
   are conditional on never being margin-called — which is a
   conditional that fails in real markets. NOT modeled.

6. **Cash management around overnight gaps.** Futures continue trading
   nearly 23 hours/day. Overnight gaps can move the position before
   you wake up. Shares only move during RTH. Real concern for sized
   positions.

## Decision rule application

User-locked criteria revisited with leverage-targeting data:

> If futures lift comparable to share lift (within 50%): generalizes,
> deploy candidate.

**PASS.** Sortino lift is essentially identical (3.82 vs 3.83). The rule
generalizes cleanly across all leverage levels.

> If futures lift higher after taxes/rolls: deploy on futures.

**PASS in principle.** At any deployable leverage, futures' Section
1256 advantage compounds and dominates shares after-tax. But this
assumes the leverage is achievable AND the trader survives the
drawdown.

> If futures lift lower: deploy on shares.

Doesn't apply.

> If futures break the rule: edge may be share-specific.

REFUTED. The edge is the rule's signal, not the vehicle.

## My recommendation — Shares 1x at $8k, futures migration at $25k+

This is the path that actually holds up to operational reality:

**Phase 1: Deploy shares (QQQ or SPY) with the SMA(50)/(200) gate.**

  - Capital: $8k taxable, all in.
  - Expected after-tax CAGR (lower bracket): **+18-29%** depending on regime.
  - Drawdown: −10 to −15%. Manageable.
  - Operational complexity: minimal. Buy/sell at close on signal flips.
  - Margin call risk: zero.
  - Deployable now.

  Trade-off: forfeits Section 1256 tax advantage. Shares lose
  ~9-13 percentage points of after-tax CAGR vs equivalently-leveraged
  futures.

**Phase 2: Migrate to 1 MES futures when account reaches ~$15-20k.**

  - At $15k: 1 MES = 1.9x leverage (close to user-spec 2.0x target)
  - Captures Section 1256 advantage.
  - Frees ~$13k for diversifier strategies (the multi-strategy thesis
    finally becomes viable).
  - Margin call buffer expands proportionally.

**Phase 3: Add MNQ if account grows beyond $50k.**

  - At $50k: 1 MNQ = 0.8x leverage (sub-1x), 2 MNQ = 1.6x (close to target)
  - Higher liquidity, smaller per-tick risk in absolute terms.

**Why not 1 MES at $8k now?**

  - +90% theoretical CAGR is appealing
  - But 22% SPX drop = margin call. 1987 and 2020 prove this can happen.
  - At $8k, getting margin-called means losing the account, not just
    a bad year.
  - The Sortino is the same as 1x — leverage doesn't improve risk-adjusted
    returns, it just amplifies both directions.

**Why not 1 MNQ at $8k?**

  - 16% NDX drop = margin call. Has happened multiple times in
    2018-2026 alone (March 2020, June 2022, October 2022).
  - 1 MNQ at $8k is a "blow up before edge plays out" trade.
  - Don't do it.

## What this means for the multi-strategy thesis

The user's earlier framing: lift component + diversifier. With shares at
1x as the lift component:

- **Capital used by lift component: 100% of $8k**
- **Capital free for diversifier: ~0%**

So at $8k with shares, multi-strategy is NOT viable. We'd be running a
single-strategy portfolio. That's defensible — Tier-A standalone is
better than Tier-B with diversifier in some framings — but it's not
the multi-strategy thesis.

For multi-strategy to work as articulated, we need either:
1. **Account growth to $25k+** so 1 MES at 2x leverage uses 10% of
   capital and frees the rest.
2. **Different vehicle** that allows fractional leverage at $8k. Options
   could work (LEAPS for trend exposure with delta < 1) but introduces
   complexity orthogonal to the trend rule.

Practical answer: deploy shares now, grow account, expand to multi-strategy
at $25k+. The strategy itself is robust enough that a few years of
disciplined deployment should reach that threshold.

## Discipline reminders

Per locked rules:
- No MA window tuning. 50/200 stays.
- No leverage tuning beyond what the user specified (1x, 1.5x, 2.0x).
- No "what if I rebalance more frequently" iterations.
- One look at the data, one decision.

The decision is: **deploy shares at 1x. Migrate when account grows.**

## Files

- `scripts/run_bah_leverage_tax.py` — runner
- `reports/bah_leverage_tax/raw_output.txt` — full output
