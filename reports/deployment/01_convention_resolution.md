# Item 1 — Convention resolution

**Date:** 2026-05-03
**Branch:** claude/strategy-validation-v2
**Script:** `scripts/run_realistic_backtest.py`
**Raw output:** `output_realistic.txt`

## Decision

**Deployment uses Convention 2 (MOC) as the primary execution path, with
Convention 3 (next-day open) as the documented fallback. Both produce
nearly identical results for this strategy. Tier-A status is NOT met
under realistic execution; the strategy operates as a regime-conditional
defensive overlay (per consolidated analysis).**

## Convention retracing — what's actually achievable

The labels in prior tests had me flipping between which was "lookahead"
and which was "realistic." After careful re-derivation:

- The signal `flag[t]` requires `close[t]` to compute (it uses an SMA
  over closes through day t).
- To capture the return `ret[t] = close[t]/close[t-1] - 1` as a long
  position, you must have been long *going into* day t — i.e., long at
  `close[t-1]`.
- That requires a decision at or before `close[t-1]`, which uses
  `flag[t-1]` (the SMA computed using closes through `t-1`).

**Therefore: realistic MOC convention is `flag[t-1] → ret[t]`**. This is
what I had been calling Convention 2.

Convention 1 (`flag[t] → ret[t]`) is pure lookahead — no operational path
exists. It was wrong from the start, not just biased.

## MOC operational viability on IBKR

**Confirmed achievable.** Specifics:

| Item | Detail |
|---|---|
| QQQ exchange | NASDAQ |
| NASDAQ MOC submission cutoff | **15:55 ET** |
| NASDAQ MOC cancel/modify cutoff | **15:50 ET** |
| Order fills at | Official 16:00 ET closing auction |
| IBKR Lite commission on QQQ | **$0** (commission-free US ETFs) |
| IBKR Pro Fixed commission | $0.005/share, $1 minimum |
| QQQ typical bid-ask spread (2024-2026) | $0.01–$0.02 on ~$500 share = 0.2–0.4 bps |

**Recommendation:** Use **IBKR Lite** for the deployment account. Zero
commission means our friction is purely slippage (1 bp/fill conservative
estimate, see below).

**Workflow:**
1. At ~15:45 ET, compute SMA(50)/(200) using last completed bar (15:45 print)
   as proxy for close.
2. Compare with prior day's signal. If state changed, prepare MOC order.
3. Submit MOC by 15:55 ET cutoff. Order fills in 16:00 closing auction.
4. The signal-at-15:45 vs signal-at-close-actual difference is small for
   liquid ETFs — typically <2 bps price drift in last 15 minutes for QQQ.
5. Edge case: if signal flips between 15:45 and 16:00 due to a late move,
   you'll execute on the 15:45 reading (slightly stale signal). Acceptable.

## Final realistic backtest results (Convention 2 with costs)

### QQQ 2000-2026 (modern era, 26 years)

| Convention | Sortino | CAGR | AT-CAGR | |DD| | Trans/yr | Final $ |
|---|---:|---:|---:|---:|---:|---:|
| Buy-and-hold (no strategy) | 0.57 | +7.4% | n/a | 83% | — | $52,128 |
| Conv 2 (MOC), zero costs | 0.82 | +6.2% | +5.3% | 22% | 12.58 | $38,748 |
| **Conv 2 (MOC), 1bp slippage/fill** | **0.81** | **+6.1%** | **+5.2%** | **23%** | **12.58** | **$37,490** |
| Conv 2 (MOC), 5bp slippage (stress) | 0.74 | +5.5% | +4.7% | 25% | 12.58 | $32,853 |
| Conv 3 (next-day open), 1bp | 0.81 | +6.1% | +5.2% | 23% | 12.58 | $37,532 |

### ^GSPC 1928-2026 (full 98-year history)

| Convention | Sortino | CAGR | AT-CAGR | |DD| | Trans/yr | Final $ |
|---|---:|---:|---:|---:|---:|---:|
| Buy-and-hold (no strategy) | 0.57 | +6.0% | n/a | 86% | — | $2.26M |
| Conv 2 (MOC), zero costs | 0.97 | +5.9% | +5.6% | 37% | 11.34 | $2.21M |
| **Conv 2 (MOC), 1bp slippage/fill** | **0.96** | **+5.8%** | **+5.5%** | **37%** | **11.34** | **$1.98M** |
| Conv 2 (MOC), 5bp slippage (stress) | 0.88 | +5.3% | +5.1% | 38% | 11.34 | $1.27M |
| Conv 3 (next-day open), 1bp | 0.91 | +5.6% | +5.3% | 34% | 11.34 | $1.59M |

**Key findings:**

1. **Conv 2 vs Conv 3 spread is small.** ~10 bps CAGR difference on QQQ
   sample, ~20 bps on the 98-year sample. The MOC advantage exists but
   is minor — overnight gaps don't systematically work against the
   strategy in the entry/exit pattern.

2. **Slippage at 1 bp/fill costs ~10 bps CAGR.** At 12.58 transitions/yr,
   the friction drag is trivial. At 5 bp (stress scenario), drag is
   ~70 bps CAGR — still acceptable.

3. **Tier A is NOT met under realistic convention** (Sortino 0.81 < 1.5).
   This is consistent with the consolidated analysis. Strategy operates
   as a regime-conditional defensive overlay, not a Tier A monolith.

4. **Strategy still beats BAH on Sortino** under realistic costs:
   - QQQ 2000-2026: +0.24 Sortino (0.81 vs 0.57)
   - ^GSPC 98-yr: +0.39 Sortino (0.96 vs 0.57)

5. **Drawdown reduction is preserved** — 60pp on QQQ (83% → 23%), 49pp
   on ^GSPC (86% → 37%).

## Friction details surfaced

Items previously not modeled in the backtest:

| Item | Cost estimate | Modeled? | Notes |
|---|---|---|---|
| QQQ commission (IBKR Lite) | $0 | n/a | Commission-free |
| QQQ slippage at MOC | 0.2–0.4 bps half-spread | 1 bp buffer included | QQQ is one of the most liquid ETFs |
| SGOV commission (IBKR Lite) | $0 | n/a | Commission-free |
| SGOV slippage | 0.5–1 bp half-spread | 1 bp buffer included | Lower volume than QQQ but very liquid |
| SEC fee (sell side, ETFs) | $0.0000278/dollar = ~0.003 bps | not modeled | Negligible |
| FINRA TAF | $0.000166/share (capped) | not modeled | <$0.10 per trade |
| Per-trade min commission (Pro) | $1 | not applicable on Lite | n/a |
| 24-month inactivity fee (Pro) | $10/mo if <$10 commission/mo | n/a on Lite | Lite has no inactivity fee |

**Total deployable friction: ~10 bps/yr at 12.58 transitions × 1 bp slippage.**
Conservative buffer: 25 bps/yr including unmodeled SEC/FINRA fees and
occasional slightly worse fills.

## Realistic deployable performance envelope

Combining all the above, the realistic forward-looking expected performance
for QQQ shares 1x + 50/200 SMA + T-bill OFF on IBKR Lite:

| Metric | Expected (1bp slippage) | Stress (5bp slippage) | BAH benchmark |
|---|---:|---:|---:|
| Pre-tax CAGR | +6.1% | +5.5% | +7.4% |
| After-tax CAGR (24% STCG) | +5.2% | +4.7% | ~+6.5% |
| Sortino (vs T-bill) | 0.81 | 0.74 | 0.57 |
| Max drawdown | 23% | 25% | 83% |
| Annual transitions | ~12 (round-trip ~6) | same | n/a |

**Probability-weighted across the 98-year regime distribution** (per the
consolidated analysis, Sortino 0.96 across full ^GSPC history with 1bp
slippage):

- ~15-20% probability of bear regime windows where strategy adds
  +3-9 pp/yr CAGR over BAH
- ~60-70% probability of bull regime windows where strategy lags BAH
  by 2-9 pp/yr CAGR
- Net expected: roughly match BAH CAGR, +0.4 Sortino lift, dramatic
  drawdown reduction

## Item 1 conclusion

**Convention question RESOLVED.**

- Convention used: **Convention 2 (MOC)** with **Convention 3 (next-day
  open) as documented fallback**. Both are nearly equivalent.
- MOC viable on IBKR Lite for QQQ (NASDAQ): yes, 15:55 ET cutoff.
- Commission: $0 on IBKR Lite for US ETFs.
- Slippage: model 1 bp/fill (conservative); stress at 5 bp.
- After-tax expected CAGR: +5.2% (1bp) to +4.7% (5bp stress).
- Tier A NOT met under realistic convention; deployment narrative
  remains "regime-conditional defensive overlay."

**Sources for the operational facts:**
- IBKR Pricing — [Commissions Stocks](https://www.interactivebrokers.com/en/pricing/commissions-stocks.php), [IBKR Lite vs Pro](https://www.matchmybroker.com/articles/ibkr-lite-vs-ibkr-pro)
- NASDAQ MOC cutoff times — [Order Types Reference](https://www.interactivebrokers.com/en/trading/orders/moc.php) (cutoffs: 15:50 ET cancel/modify, 15:55 ET submission)
