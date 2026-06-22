# Operational Deployment Scoping — Honest Estimate

**Date:** 2026-06-22
**Goal:** scope the engineering work to reach paper-trading start for the
validated static-50/50 QQQ-trend + BTC-trend portfolio.

---

## The headline finding (read this first)

**Most of the existing operational code targets a strategy we abandoned.**

The repo contains a substantial operational system — `src/runner/` (466-line
orchestrator), `src/strategies/` (EWO, IBS, afternoon), `src/risk/`
(weekly budget, guardrails, blackout), `src/positions/` (manager, exits) —
but it was all built for the **original options-trading concept**: trading
short-dated options on ETFs with intraday FillChase limit-order ladders,
weekly premium-loss budgets, deferred-entry-at-next-open queues, and
options-Greek risk caps.

The validated strategy is **dramatically simpler**:
- Daily check: is `close > SMA50 > SMA200` for QQQ? for BTC?
- If ON and flat → buy. If OFF and holding → sell, move to T-bill vehicle.
- Static 50/50 across two sleeves. No options, no intraday, no FillChase,
  no premium budget, no Greeks.

So the honest reuse picture is **"salvage 3 components, rewrite the rest
simpler"** — not "extend the existing runner." Trying to bend the
options-runner to this strategy would be more work than a clean, small
build. The config (`src/config.py`) is entirely options concepts
(`max_gross_premium_pct`, `weekly_loss_budget_usd`, `ewo_enabled`) and
will be replaced by the basket config (already built — see below).

### What's genuinely reusable

| Existing component | Reuse | Why |
|---|---|---|
| `src/runner/ibkr_adapter.py` — stock-order plumbing | **Partial** | Has `Stock(symbol, "SMART", "USD")` + `LimitOrder` + `placeOrder` + position/equity queries. Needs MOC order support added and the options paths stripped. ~40% reusable. |
| `src/runner/store.py` — atomic-JSON persistence | **Pattern** | The write-temp-then-rename atomic-save pattern is exactly right. The schema it persists (options positions, weekly budget) is wrong. Reuse the pattern, new schema. |
| `src/runner/sim.py` — in-memory broker/feed for tests | **Pattern** | The deterministic test-double pattern is reusable; the specifics target options. |
| `src/data/yahoo.py`, `src/data/fred.py` | **Yes** | QQQ/BTC daily bars + T-bill rate. Already used in research. |
| `src/deploy/baskets.py` (NEW, built today) | **Yes** | Basket weights + sizing + vehicle resolution. Done. |

### What's NOT reusable (built for the abandoned strategy)

`src/strategies/*` (EWO/IBS/afternoon), `src/risk/*` (weekly budget,
guardrails, blackout/regime for options), `src/positions/*` (options
position lifecycle), the 466-line `runner.py` orchestration, `src/config.py`,
`src/backtest/*` (research engines, not live), `src/broker/orders.py`
FillChase ladder.

These don't get deleted (they're the record of the original concept) but
they are **not the foundation** for the deployment.

---

## The 13 items — honest status and effort

Effort in **working days** of focused engineering. "Exists" = usable as-is
or near-as-is; "Partial" = salvageable component needs adaptation; "Build" =
from scratch (but simple).

### Priority 1 — must resolve before paper trading (items 1-6)

| # | Item | Status | Effort | Notes |
|---|---|---|---|---|
| 1 | **MOC vs next-day-open fill convention** | Decision | 0.5d | *Decision, not code.* See "Item 1 resolution" below — recommend **next-day market-on-open** for both sleeves. Resolving the 15pp/yr question: it was a *backtest-convention* artifact, not a live choice. |
| 2 | **OFF-vehicle selection (SGOV/USFR/SHV/BIL)** | Decision | 0.25d | *Decision, mostly done.* Recommend **SGOV**. See "Item 2 resolution." Document + set in config. |
| 3 | **Tax-lot accounting workflow** | Decision + doc | 0.5d | *Decision + documentation.* Recommend **specific-identification (HIFO)** at IBKR for the taxable account; document the loss-tracking + 1099-B reconciliation workflow. No code (IBKR handles lots). |
| 4 | **Daily close-check job (4pm ET)** | Build | 2d | The heart of the system. Pulls QQQ+BTC daily bars, computes SMA50/SMA200, determines filter state per sleeve, compares to stored state, logs state + any change. Simple but must be correct + robust. |
| 5 | **Alerting on filter state changes** | Build | 1d | Email (SMTP) or SMS (Twilio) when a sleeve flips ON/OFF. One channel for paper. |
| 6 | **Order placement workflow** | Partial→Build | 2d | Salvage `ibkr_adapter` stock plumbing; add the market-on-open (or MOC) order path + fill confirmation + reconciliation. Strip options paths. |

**Priority 1 subtotal: ~6.25 days** (of which 1.25d is decisions/docs, 5d is code).

### Priority 2 — needed for clean paper trading (items 7-10)

| # | Item | Status | Effort | Notes |
|---|---|---|---|---|
| 7 | **Position tracking, per-strategy + per-basket** | Build | 1.5d | New schema (reuse `store.py` atomic-save pattern). Tracks per-strategy LONG/FLAT, entry price/date, shares/contracts; aggregates to basket + portfolio. The basket layer (`src/deploy/baskets.py`) already provides the aggregation structure. |
| 8 | **P&L tracking, per-strategy + per-basket** | Build | 1d | Daily mark-to-market per sleeve; realized + unrealized; aggregate to basket. Builds on #7. |
| 9 | **Tax tracking infrastructure** | Build | 1d | Log every realized lot (open date, close date, proceeds, basis, ST/LT, wash-sale flag for QQQ shares). Feeds year-end reconciliation against IBKR 1099-B. |
| 10 | **Reconnect/restart resilience** | Build | 1.5d | Daily-check job must survive: IBKR disconnect, data outage, container restart. Idempotent operations + a startup reconciliation pass ("what does the broker hold vs what does my state say"). |

**Priority 2 subtotal: ~5 days.**

### Priority 3 — basket architecture (items 11-13)

| # | Item | Status | Effort | Notes |
|---|---|---|---|---|
| 11 | **Basket-weight config system** | **DONE** | 0d | Built today: `config/baskets.json` + `src/deploy/baskets.py` + 8 passing tests. Config-driven weights, validates sum-to-1.0, resolves vehicles by account size. |
| 12 | **Rebalancing rules + triggers** | Decision + Build | 1d | *Decision done in config:* **drift-band, 10% relative**, acted on only at filter transitions (no standalone rebalance trades in Stage 1 — the 50/50 two-sleeve book barely drifts and rebalancing it would just add taxable events). Light code to enforce the band when a transition trade happens. |
| 13 | **Per-basket P&L + drawdown reporting** | Build | 1d | Extends #8 with basket-level drawdown + a daily reconciliation report. |

**Priority 3 subtotal: ~2 days** (item 11 done; 2 days remaining).

---

## Order of operations (what blocks what)

```
DECISIONS (do first, ~1.5d, no code dependencies)
  1. MOC vs next-day-open      ─┐
  2. OFF-vehicle (SGOV)         ├─► unblock everything; set in config
  3. Tax-lot workflow          ─┘
  12. Rebalance policy (done in config)

FOUNDATION (build next)
  6. Order placement  ──────────► depends on decision #1
  4. Daily close-check job ─────► depends on nothing (can start immediately)
  7. Position tracking ─────────► depends on #4 producing state
        │
        ├─► 8. P&L tracking ────► depends on #7
        │      └─► 13. Basket P&L/DD reporting
        ├─► 9. Tax tracking ────► depends on #7
        └─► 10. Restart resilience ──► depends on #4 + #7 (reconciliation)

  5. Alerting ──────────────────► depends on #4 (consumes state-change events)

INTEGRATION
  End-to-end dry run in IBKR paper (signal computed → order placed →
  fill confirmed → state persisted → alert fired) before "paper start".
```

The **critical path** is: decisions (1.5d) → daily-check job (#4, 2d) →
position tracking (#7, 1.5d) → order placement (#6, 2d, can parallelize with
#7) → restart resilience (#10, 1.5d) → integration dry-run (1d). That's
~8-9 days on the critical path; the rest (alerting, P&L, tax, basket
reporting) parallelizes.

---

## Realistic timeline to paper-trading start

**3 weeks** (15 working days), not 2. Honest breakdown:

| Phase | Days | Calendar |
|---|---|---|
| Decisions + config (items 1,2,3,12) | 1.5 | Week 1, days 1-2 |
| Daily-check job + order placement (4, 6) | 4 | Week 1, days 3-5 + Week 2 day 1 |
| Position + P&L + tax tracking (7, 8, 9) | 3.5 | Week 2 |
| Alerting + resilience + basket reporting (5, 10, 13) | 3.5 | Week 2-3 |
| Integration dry-run + paper-account verification | 2 | Week 3 |
| Buffer (IBKR paper API quirks, MOC routing confirmation) | 1.5 | Week 3 |

**Why 3 weeks not 2:** the earlier 2-week estimate (`DEPLOYMENT_SCOPING.md`)
assumed more of the existing runner was reusable. Having surveyed it, the
options-runner doesn't fit, so #6 (order placement) and the orchestration
are closer to fresh builds. The work is *simple* (the strategy is trivial
operationally) but it's still ~15 days of careful, tested code + the
unavoidable IBKR-paper integration friction.

**Surprise risks honestly flagged:**
1. IBKR paper API behaves differently from live (delayed fills, market-data
   subscription quirks, order-type routing). Budgeted in the 1.5d buffer.
2. BTC 24/7 timing: crypto never closes. The "daily check" needs a fixed
   reference time (recommend 4pm ET aligned with the equity close, using the
   00:00-UTC daily bar for BTC). Decision folded into #4.
3. IBIT (the BTC vehicle) trades market hours only, while the BTC *signal*
   is computed on 24/7 data. Small timing mismatch; immaterial for a daily
   strategy but documented.

---

## Priority-1 decision resolutions (the 3 that gate everything)

### Item 1: MOC vs next-day-open → **next-day market-on-open**

The "15pp/yr spread" was a *backtest-convention* finding, not a live-execution
choice. Recap: Convention 1 (`flag[t]→ret[t]`, same-bar) is unachievable
live (you can't trade on a close you haven't seen). Convention 2
(`flag[t-1]→ret[t]`, decide at yesterday's close, capture today's return)
is the honest, deployable convention — and it's what all the validated
results use. **The deployment uses Convention 2: compute the filter at the
4pm ET close, place the order for the next session.**

- **For QQQ shares:** market-on-open (MOO) at next-day 9:30 ET, OR a
  marketable limit in the first minute. MOO is simplest; the QQQ open is
  deeply liquid so slippage is minimal.
- **For IBIT:** same — MOO next session. IBIT opens with the equity market.
- **MOC alternative considered and rejected for Stage 1:** MOC (market-on-
  close, same day the signal computes) would require computing the signal
  *before* the close it's based on — a look-ahead. Not used.

This means the strategy formally trades with a one-session lag (signal at
close N, fill at open N+1). The validated backtests already assume this lag
(Convention 2 with the `.shift(1)` discipline), so live ≈ backtest.

### Item 2: OFF-vehicle → **SGOV**

| Vehicle | Expense | Yield basis | Liquidity | Verdict |
|---|---|---|---|---|
| **SGOV** | **0.09%** | 0-3mo T-bills | very high | **Selected** |
| BIL | 0.1357% | 1-3mo T-bills | very high | higher fee |
| SHV | 0.15% | <1yr T-bills | high | higher fee, longer duration |
| USFR | 0.15% | floating-rate notes | high | FRN basis differs; higher fee |

SGOV: lowest expense ratio, shortest duration (least rate-risk on the OFF
parking), deeply liquid, distributes monthly. Set as `off_vehicle: tbill`
→ resolves to SGOV in the order layer. Documented.

### Item 3: Tax-lot workflow → **specific-identification (HIFO) at IBKR**

- **Method:** specific-identification, highest-in-first-out (HIFO) default,
  set in IBKR account config. Minimizes realized gains on each exit (sells
  highest-cost lots first), deferring tax.
- **Loss tracking:** every realized lot logged by the tax-tracking module
  (#9): open/close dates, proceeds, basis, ST vs LT, and a **wash-sale flag
  for QQQ shares** (the 50/200 whips ~6×/yr; some round-trips realize losses
  that wash-sale rules disallow if re-entered within 30 days — flag them).
  Note: IBIT/MBT/MNQ futures (§1256) are wash-sale-exempt; only QQQ *shares*
  need wash-sale tracking.
- **Year-end:** the module's lot log reconciles against IBKR's consolidated
  1099-B. Discrepancies (rare) get investigated; the 1099-B is authoritative
  for filing.

---

## Diversifier baskets — commodities + bonds (your request)

You asked to have commodities and bonds available "in there for the
diversifiers." Done architecturally:

- **Basket 4 (moderate growth w/ diversification):** commodity long-short V3
  filed as candidate. `enabled: false, weight: 0`. Activation criteria in
  config: account ≥ $25k + fresh re-validation.
- **Basket 5 (complex multi-strat diversification):** bond trend 50/200
  filed as candidate. `enabled: false, weight: 0`. Activation note: deploy
  small (5-10%) as a crisis overlay only when account size tolerates a
  low-standalone-return sleeve for its diversification value.

Both are **config-activatable without code changes** — flip `enabled: true`,
set a weight, rebalance the others to keep the sum at 1.0, and the sizing
layer picks them up. They are NOT deployed in Stage 1 (both currently 0%).

**Honest note:** neither cleared Tier B as a standalone deployable. Bonds
were Tier D on standalone Sortino despite real diversification properties
(−0.29 corr, 4/4 stress wins, dodged 2022). Commodities were a Tier C
near-miss deferred to $25k+. Filing them in the basket structure makes them
*available* for a future deliberate decision to add a small diversifier
sleeve — it does not change the verdict that neither earns a Stage-1 slot.
When you want to actually run a diversifier sleeve, it should be a conscious
"I'll accept lower standalone return for the crisis hedge" decision, sized
small, not an automatic deployment.

---

## Paper-trading parameters (locked, recorded here)

- **Duration:** 6 months minimum.
- **Weighting:** static 50/50 (Basket 2 / Basket 3), per `config/baskets.json`.
- **Account:** IBKR paper, verified to support QQQ shares + IBIT (both are
  standard US-listed; verification is part of the integration dry-run).
- **Capture:** actual fill quality vs backtest assumptions (slippage per
  fill, signal-to-fill timing) for both sleeves.
- **Document:** operational issues as they surface.
- **End of paper:** compare realized vs backtested performance for the period.

## Go / No-Go (locked)

**GO — all must hold:**
1. Realized fill quality within 25% of backtest assumptions, both sleeves.
2. No critical operational failures during the paper period.
3. Operator has not overridden the bot during the paper period.
4. Tax-lot tracking confirmed working.

**NO-GO — any one disqualifies:**
1. Realized fills >50% worse than backtest assumptions.
2. Operational failures that aren't easily fixable.
3. Operator overrode the bot more than once during paper.

## Strategy abandonment (locked)

Revert to broad-market index buy-and-hold if any of:
1. 12 months live underperforms QQQ buy-and-hold by >5pp net of tax.
2. A sequence of 4+ false-signal whipsaws within 18 months.
3. Realized after-tax return underperforms inflation by >2pp over any
   24-month window.

---

## Recommended first actions (not auto-executed)

1. **Day 1:** lock the three decisions (items 1, 2, 3) — I've recommended
   next-day-open, SGOV, HIFO above. Confirm or override, and I commit them.
2. **Days 2-4:** build the daily close-check job (#4) — the foundation.
3. **Days 5-6:** order placement (#6), salvaging the IBKR stock plumbing.
4. Then position/P&L/tax tracking, resilience, alerting, integration.

I've built the basket architecture (item 11) today. Tell me which item to
build next, or to proceed down the critical path in order.
