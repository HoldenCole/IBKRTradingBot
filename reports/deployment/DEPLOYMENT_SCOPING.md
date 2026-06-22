# 2-Week-to-Paper-Trading Scoping (honest)

**Date:** 2026-06-22
**Status:** Diversifier search closed. Deployable architecture locked.
**Goal:** stand up automated paper trading of the QQQ + BTC sleeves with
production-grade execution discipline.

## What's already built and validated (≈70% of the work)

This is the part of the system that's been built across the research
rounds and is reusable for live deployment:

- **Strategy logic locked:** QQQ 50/200 SMA + close > SMA50; BTC 50/200 SMA;
  T-bill OFF treatment; signal at close[t-1] drives position from close[t-1]
  to close[t] (Convention 2, no look-ahead — locked).
- **Backtest engine + signal modules:** `src/commodity/signals.py::sma_crossover`,
  `src/crypto/engine.py::run_long_flat`, daily-bar runners — these compute
  the *exact same signals* the live system will use. Code reuse means we're
  not re-implementing the signal logic for production.
- **Data loaders:** Databento (paid, working) and yfinance fallback for QQQ
  and BTC; cached with hygiene checks.
- **IBKR adapter sketch:** `src/runner/ibkr_adapter.py` (from much earlier in
  the project) has the connection-mgmt skeleton. Needs review + completion.
- **Reports infrastructure:** trade-log + daily-snapshot patterns established;
  reuse for live.

## What's NOT built — the honest 2-week list

Ordered by criticality. "Days" are working days of focused effort.

### Critical path (must-have before paper trading begins)

| # | Item | Effort | Notes |
|---|---|---|---|
| 1 | **MOC/timing resolution** | 0.5d | Documented decision: use MOC orders for QQQ; mid-day check for BTC (24/7). Commit the operational decision; no code yet. |
| 2 | **OFF-vehicle selection (SGOV)** | 0.5d | Read the existing analysis in `reports/deployment/02_off_vehicle_decision.md` if present; otherwise pick SGOV (lowest TER, monthly distributions, no surprises). Commit the decision. |
| 3 | **IBKR adapter — finish + test against paper account** | 2d | Existing skeleton needs: order placement (MKT, MOC, MOO), order status reconciliation, position query, account-equity query, error handling. Test against IBKR paper account. |
| 4 | **Daily close-check job** | 1.5d | Cron/scheduler entry point that: (a) pulls latest QQQ + BTC closes, (b) computes SMA50/SMA200 + signal state for each, (c) compares to previous day's stored state, (d) triggers entry/exit if changed, (e) writes state file + log. The state-machine logic, not the broker calls (those live in #3). |
| 5 | **Position-state persistence** | 1d | Sqlite or JSON-file store: current position per sleeve (LONG/FLAT, entry date, entry price), pending orders, last-signal-state, last-rebalance-timestamp. Resilient to restart (the system must be able to crash and resume without double-entering). |
| 6 | **Tax-lot accounting workflow** | 0.5d | Decision + documentation: use FIFO at IBKR (default), document expected wash-sale events on QQQ whipsaw weeks, note IBIT 1099-B treatment + spot crypto property treatment. Not code; an operational decision doc. |

**Critical-path subtotal: ~6 days.**

### Important (needed within the first 2 weeks of paper)

| # | Item | Effort | Notes |
|---|---|---|---|
| 7 | **Alerting layer for state changes** | 1d | Email/SMS/Discord on: signal flip, order placed, order filled, order rejected, daily summary. One channel is enough for paper; multiple channels = production. |
| 8 | **Reconnect/restart resilience** | 1d | Job must survive: IBKR disconnect, brief data outage, container restart, machine reboot. Idempotent operations + reconciliation pass on startup ("what does the broker say I'm holding vs what does my state file say"). |
| 9 | **Daily reconciliation report** | 0.5d | End-of-day snapshot: position vs target, P&L vs benchmark (BAH), drift checks, deviation log. Generated automatically; reviewed manually for a few weeks. |
| 10 | **Pre-flight checks** | 0.5d | Startup script that verifies: IBKR connection healthy, market data flowing, account equity matches expectation, sleeve allocations within bounds. Refuses to trade if any check fails. |

**Important subtotal: ~3 days.**

### Optional polish (during paper period, not blocking)

| # | Item | Effort | Notes |
|---|---|---|---|
| 11 | Better dashboard (web UI) | 2d | Nice-to-have; logs + reconciliation report are enough for paper |
| 12 | Multi-sleeve allocation logic | 1d | Currently each sleeve runs independently with fixed $ allocation; later we may want dynamic rebalancing |
| 13 | Anomaly detection / circuit breakers | 1.5d | Auto-pause on unexpected positions, oversized orders, repeated rejections |

**Optional subtotal: ~5 days (deferred).**

## Honest timeline

- **Critical path (items 1-6): ~6 working days** — a focused week.
- **Important (items 7-10): ~3 working days** — second week, ideally
  running in parallel with the first week of paper trading.
- **Total to "paper trading running with confidence": ~9 working days = ~2
  weeks** assuming no surprises.

Surprise risks that could blow this estimate (calling them out honestly):

1. **IBKR paper API quirks.** Paper accounts sometimes behave differently
   from live (delayed fills, market-data subscription quirks, MOC routing
   differences). Discovered only on contact. Mitigant: budget 2d for the
   adapter (item 3) rather than 1d.
2. **MOC order routing.** Mentioned in the user message as the "15pp/yr
   Convention 1/2 spread" — needs operational confirmation that the bot's
   MOC orders are actually routing to the closing auction and not being
   converted to limit orders. Worth one round-trip with IBKR support before
   trusting MOC for live.
3. **BTC 24/7 timing.** Crypto doesn't close. The "daily" check timing has
   to be picked (00:00 UTC? 16:00 ET aligned with equity close?). Decision +
   implementation = 0.5d that's not separately accounted for; folded into
   item 4.
4. **Tax-lot wash-sale events on whipsaw weeks.** Not blocking but during
   weeks where 50/200 flips repeatedly, the operator (you) needs to
   understand how wash sales are reported on 1099-B. One conversation with a
   tax-aware person, not the bot's problem.

## What "ready to paper-trade" actually means

A binary checklist — when all of these are ✓, paper trading begins:

- [ ] Strategy spec documented + locked (already done: `DECISIONS.md`)
- [ ] OFF vehicle selected + documented
- [ ] MOC routing decision documented + tested in IBKR paper
- [ ] IBKR adapter handles: connect, place order, check fill, query
      position, query equity, reconnect, errors
- [ ] Daily close-check job runs to completion without intervention
- [ ] Signal state persists across restarts
- [ ] Pre-flight checks gate trading
- [ ] At least one full no-op day-to-day cycle has run in paper
      (signal computed, no action needed, no errors)
- [ ] At least one full entry/exit cycle has run in paper (forced
      transition or natural — tests the full path)
- [ ] Alerting is wired up to a channel the operator (you) actually
      checks
- [ ] Tax workflow documented (not implemented — paper doesn't tax)

Once these all check, paper begins. Plan for **2 weeks of paper before any
live capital**, minimum, with daily reconciliation review.

## Recommendation on first steps (not auto-executing)

If you want to start immediately:

1. **Day 1:** Items 1, 2, 6 (the documentation decisions) — half a day each,
   commit decisions to the repo, no code yet.
2. **Days 2-4:** Item 3 (IBKR adapter completion + paper test).
3. **Days 5-6:** Items 4 + 5 (close-check job + state persistence).
4. **Day 7-8:** Items 7, 8, 10 (alerting, resilience, pre-flight).
5. **Day 9:** End-to-end dry run in paper account.
6. **Day 10+:** Paper trading running; item 9 reports come in daily.

Or any subset of this you want me to scope/execute individually.

## What's NOT in this path

The parallel research queue (see `RESEARCH_QUEUE.md`) is explicitly **not
gating** deployment:

- TQQQ trend with leveraged-ETF decay modeling
- 1 MES leverage research at account-size-conditional thresholds
- (Crypto futures vehicle decision is already done — `02_vehicle_analysis.md`)

These can run in parallel or be deferred entirely. When/if they validate,
the deployed portfolio reweights via config change, not code change.
