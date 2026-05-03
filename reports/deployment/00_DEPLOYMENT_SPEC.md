# Deployment Spec — locked

**Date locked:** 2026-05-03
**Branch:** claude/strategy-validation-v2
**Status:** Pre-deployment items 1, 2, 3 RESOLVED. Ready for paper trading.

This is the authoritative deployment spec. Other documents in this
directory (01, 02, 03) are the underlying analyses.

---

## Strategy

```
Long instrument:    QQQ shares (1x leverage)
Trigger:            SMA(50) > SMA(200) AND close > SMA(50)
Decision frequency: Daily, at 15:45 ET (10 minutes before MOC cutoff)
Execution:          Market-on-Close (MOC) orders, 15:55 ET cutoff
ON treatment:       100% QQQ
OFF treatment:      100% SGOV (iShares 0-3 Month Treasury, 0.07% ER)
Backup OFF vehicle: BIL (if SGOV ever has liquidity issues)
Initial capital:    $8,000
Account type:       IBKR Lite, Texas-resident taxable brokerage
Lot-matching:       FIFO (default, moot since 100%-sell on each exit)
```

## Realistic deployable performance (with costs)

From `reports/deployment/01_convention_resolution.md`:

| Metric | Expected (1bp slippage) | Stress (5bp slippage) | BAH benchmark |
|---|---:|---:|---:|
| Pre-tax CAGR | +6.1% | +5.5% | +7.4% |
| After-tax CAGR (24% STCG) | +5.2% | +4.7% | ~+6.5% |
| Sortino vs T-bill | 0.81 | 0.74 | 0.57 |
| Max drawdown | 23% | 25% | 83% |
| Annual transitions | ~12 (~6 round trips) | same | n/a |

**Strategy provides:** ~+0.24 Sortino over BAH, drawdown reduction from
83% to 23% (60pp), at a CAGR cost of ~1.3pp.

**Long-history confirmation (^GSPC 1928-2026):** Sortino 0.96 vs BAH 0.57
across 98 years, +0.39 Sortino lift, drawdown 37% vs 86%. Strongest
single result: 1966-1982 secular bear delivered +6.4pp CAGR over BAH.

---

## Paper-trading parameters (LOCKED)

### Duration

**Minimum 6 months.** Not 3.

Rationale: 12 transitions/yr expected → ~6 transitions in 6 months.
Need to observe at least one signal change (entering OR exiting).
Probabilistically, 6 months gives ~95% chance of capturing at least
one filter state change in any non-extreme regime.

### Required observations during paper period

- At least 1 signal state change (filter ON↔OFF) — confirms execution
  path works end-to-end
- Actual fill quality measured per entry/exit:
  - MOC submission timestamp
  - Fill timestamp
  - Submission-time signal vs final-close signal (drift in last 10 min)
  - Fill price vs official close
- Operational issues logged:
  - Data feed interruptions
  - Order placement failures
  - Alert delivery (if any) reliability

### Gap analysis at end of paper period

Compare realized performance to backtest assumptions for the same
period:

| Metric | Backtest assumption | Realized |
|---|---|---|
| Avg slippage per fill (bps) | 1.0 | (measured) |
| Signal-drift error (bps from 15:45→close) | <2 | (measured) |
| Annual friction drag (bps) | ~10-25 | (measured) |
| Realized P&L vs backtested | within 25% | (measured) |

---

## GO criteria (all four must hold)

To advance from paper to live trading:

1. **Realized fill quality within 25% of backtest assumptions**
   - i.e., realized slippage ≤ 1.25 × 1bp = 1.25 bps per fill
   - Realized friction drag ≤ 1.25 × 25 bps/yr = 31 bps/yr

2. **No critical operational failures during paper period**
   - Defined: any failure that would have caused missed trades or
     incorrect trades in live mode (signal computation errors, MOC
     submission failures, broker API outages affecting order
     placement)
   - Minor issues (e.g., alert delivery delays, dashboard glitches)
     don't disqualify

3. **Operator (user) has not overridden the bot during paper period**
   - "Override" defined as: forcing a buy/sell against the bot's
     decision, OR pausing the bot for non-operational reasons (e.g.,
     "I think the market will rally, ignore the OFF signal"), OR
     adjusting parameters mid-flight
   - Operational pauses (broker maintenance, vacation with no
     internet) don't count as overrides
   - More than 0 overrides → behavioral risk; needs to be discussed
     before going live

4. **Tax-lot tracking confirmed working**
   - Year-end consolidated 1099-B from IBKR matches the bot's trade
     log
   - Wash-sale adjustments are applied as expected
   - If paper period crosses Dec 31 → Jan 1, verify wash-sale year-
     crossing handling

---

## NO-GO criteria (any one triggers)

Back to backtest/redesign rather than going live:

1. **Realized fills materially worse than backtest** (>50% gap)
   - Realized slippage > 1.5 bps per fill, or annual drag > 50 bps
   - Indicates QQQ liquidity assumption is wrong, MOC fills are bad,
     or there's a systematic problem with execution

2. **Operational failures that aren't easily fixable**
   - e.g., IBKR API limitations preventing reliable MOC submission
   - e.g., data feed quality issues affecting signal accuracy

3. **Operator has overridden the bot more than once during paper**
   - Signals behavioral risk that won't go away with live capital
   - Better to address now than after live losses

---

## Strategy ABANDONMENT criteria (LOCKED — defined now to prevent
post-hoc rationalization)

Once live, abandon and revert to broad-market index buy-and-hold if:

1. **12 months of live trading underperforms QQQ buy-and-hold by >5pp**
   - 5pp is wider than expected bull-regime underperformance (4-9pp/yr)
     so this is reasonable; tighter would risk premature abandonment
     during a normal bull regime
   - This criterion accepts that during strong bull years the strategy
     will underperform — that's by design (insurance premium)

2. **A sequence of 4+ false-signal whipsaws within 18 months**
   - Defined: 4 round-trip transitions where the round-trip P&L is
     a loss
   - Suggests a regime where the SMA crossover doesn't work
   - Historical baseline: ~3 wash-sale losses per year (sustained
     whipsaw); 4+ in 18 months is a meaningful spike

3. **Realized after-tax return underperforms inflation by >2pp over
   any 24-month window**
   - i.e., AT-CAGR < (CPI - 2pp) over rolling 24 months
   - Real returns matter; if we're losing purchasing power for 2 years,
     the strategy isn't doing its job

These are designed to prevent the most common failure mode: continuing
to run a broken strategy because the operator becomes attached to it.

**Pre-commitment:** if any of the three abandon criteria fires, the
default action is to liquidate to QQQ shares and treat the deployment
as a learning exercise. Re-evaluation requires a new validation cycle.

---

## Diversifier search — PAUSED

Per consolidated analysis: 7+ diversifier candidates have been tested
with rigorous methodology. All failed. The prior is now that clean
diversifiers are harder to find than initially assumed. Continued
search has diminishing returns.

**Resume diversifier search ONLY if:**
1. Live performance reveals a specific gap a diversifier could fill
   (e.g., bull-market underperformance becomes intolerable to operator)
2. Account grows to $25k+ (where multi-strategy with futures becomes
   viable — Section 1256 tax treatment opens up new trade-offs)
3. A specific candidate emerges from outside this analysis (e.g., new
   academic research, new ETF launch, new market structure change)

Otherwise, no further diversifier work.

---

## Sequencing (locked)

| Phase | Duration | Status |
|---|---|---|
| 1. Resolve items 1-3 | done (2026-05-03) | ✓ Complete |
| 2. Begin paper trading | 6 months | Pending |
| 3. Apply go/no-go criteria | end of paper | Pending |
| 4. Either go live or refine | based on findings | Pending |

---

## Operational checklist before paper begins

- [ ] IBKR Lite account opened and funded with paper-trading allocation
- [ ] Bot configured with exact spec above (QQQ, SGOV, 50/200, MOC)
- [ ] MOC submission window: 15:45-15:55 ET daily (cron / scheduler)
- [ ] Trade log captures all required fields (item 3 audit trail)
- [ ] Daily report email or log file showing: signal state, trades
      placed (if any), MTM equity, drift metrics
- [ ] Backup procedure: if MOC submission fails, fallback to
      next-day market-on-open (Convention 3)
- [ ] Alert on missed MOC submission (15:55 ET deadline missed)

## Files in this directory

- `00_DEPLOYMENT_SPEC.md` — this file (locked spec, go/no-go criteria)
- `01_convention_resolution.md` — Convention 1 vs 2 resolution + costs
- `02_off_vehicle.md` — SGOV vs alternatives + selection rationale
- `03_tax_workflow.md` — IBKR tax-lot mechanics + wash-sale analysis
- `output_realistic.txt` — backtest output for item 1
- `output_off_vehicles.txt` — output for item 2
- `output_wash_sale.txt` — output for item 3

---

## What "ready for paper" means

All three pre-deployment items are scoped, decided, and documented.
Realistic expected performance is bounded. Operational details
(commissions, MOC, lot-matching, wash-sale) are understood. Go/no-go
and abandonment criteria are pre-committed.

The remaining work is operational: account setup, bot configuration,
6-month paper period, then go/no-go evaluation. No further analytical
work is required to begin paper trading.
