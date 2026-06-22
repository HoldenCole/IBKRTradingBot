# Research Queue (parallel to deployment, not gating)

**Status:** Diversifier search closed. These items are *lower priority than
deployment operational work* but worth running if/when capacity allows.

**They do NOT gate deployment of QQQ + BTC.** When/if any validates, the
deployed portfolio reweights via config change, not code change.

## Queue

### 1. TQQQ trend with leveraged-ETF decay modeling — Basket 1 candidate

**Question:** does the QQQ 50/200 rule applied to TQQQ (3x leveraged) survive
the well-known volatility decay penalty? The decay is path-dependent and
mathematically eats compound returns in choppy markets — but a trend filter
that exits during chop *might* avoid the regime where decay hurts most.

**What to model honestly:**
- Daily-reset 3x leverage with realistic decay (compounded daily returns on
  the underlying × 3, not 3× the holding-period return)
- TQQQ expense ratio (~0.84%) — small but cumulative
- Bid-ask + slippage scaled appropriately (TQQQ spreads are tight)
- Whipsaw cost: 3x amplifies both the gains AND the whipsaw losses; this is
  the central honest question

**Locked criteria** (must be set before the test, per the lesson):
- Tier A: Calmar > 1.0 net of decay, MaxDD < 50%, CAGR ≥ 1.5× QQQ trend CAGR
- Tier B: Calmar > 0.7, MaxDD < 60%, CAGR ≥ 1.2× QQQ trend CAGR
- Tier C/D: standard

**Expected effort:** ~2-3 days (the infrastructure exists; just adds a
decay-correct return generator + locked-criteria evaluation).

**If it clears Tier B:** TQQQ becomes a Basket-1 leveraged alternative to QQQ
for the equity sleeve, configurable per account size. Likely deployed at
$25k+ where the larger drawdowns are tolerable.

---

### 2. 1 MES leverage research at account-size-conditional thresholds

**Question:** at what account size does it make sense to switch the equity
sleeve from QQQ shares to 1 MES (Micro E-mini S&P 500) futures? The contract
gives Section 1256 tax treatment (~26.8% blended vs 37% ST), capital
efficiency (margin << notional), and 24/5 trading. Tradeoffs are roll
mechanics, regulatory account requirements, and MES being S&P-tracking (not
Nasdaq) — which is a strategy change, not just a vehicle change.

**This is two separable questions:**

(a) **Vehicle-only:** at what account size does 1 MES (~$31k notional at SPX
6200) sleeve cleanly into the equity allocation? Similar one-pager logic to
the crypto MBT analysis already done.

(b) **Index choice:** SPX (via MES) vs NDX (via QQQ shares or MNQ futures).
This is a separate empirical test — does the 50/200 rule work the same on
SPX as on NDX? Backtest needed.

**Expected effort:** (a) 1 day, (b) 2-3 days. Can be done sequentially.

**If it clears:** account-size-conditional config that switches the equity
sleeve to MES at the right threshold.

---

### 3. CME crypto futures vehicle analysis — DONE

Already complete: `reports/crypto/02_vehicle_analysis.md`. Recommendation:
IBIT at $8k, MBT at $25k+.

This entry is here only so the queue is complete and we don't accidentally
re-run it.

---

## Priority order if capacity opens up

1. **TQQQ first** — biggest potential portfolio impact (3x leverage at the
   trend-on portion is the closest thing to a return-stage boost without
   adding new diversifier candidates we know don't exist).
2. **MES vehicle (a)** — quick one-pager, makes sense to do alongside the
   tax/operational deployment work.
3. **MES vs QQQ index choice (b)** — the longest of the three, lowest
   marginal value (we already have a working QQQ strategy).

## What's NOT in the queue (explicitly excluded)

These were considered and declined:

- **More diversifier candidates** (commodities, FX EM, FX risk-filtered).
  Diversifier search is closed per `DECISIONS.md`. Don't re-open without a
  new candidate class.
- **Norgate full-history backfill** ($270/yr). Defer until a deployable
  candidate needs the robustness test. The current near-miss (commodity
  long-short V3) is deferred to $25k+ anyway.
- **Options / VRP research.** Operationally complex, overlaps equity
  exposure, doesn't earn a Basket-1 slot.
- **ICE softs + DX completion.** Commodities shelved; complete the universe
  only if commodities are revisited.
- **Concurrent multi-test rounds.** Sequential gating worked; don't break
  the pattern.

## Trigger to revisit this queue

When (a) deployment paper trading is running stably (~2 weeks in), and
(b) you have research capacity, pick the top item and scope it like the
others.

---

# UPDATE 2026-06-22 — Queue CLEARED

All three queued items closed. Results:

1. **TQQQ trend → Tier D.** `reports/leverage/00_tqqq_trend.md`. Leveraged
   ETF + trend filter doesn't produce a Calmar improvement over unlevered
   QQQ trend. The decay penalty is partially mitigated but not enough.
2. **MES vehicle one-pager → done.** `reports/leverage/01_mes_vehicle_analysis.md`.
   Account-size threshold logic documented.
3. **MES vs QQQ index choice → MNQ wins.** `reports/leverage/02_mes_vs_qqq_index_test.md`.
   SPX trend Calmar half of NDX's — MES is a strategy change, not a vehicle
   swap. Recommended path is MNQ at $50k+.

**Queue is now empty.** Future research items go through the standard
add-to-queue process when they emerge.

Status: deployment focus is the only outstanding work stream.
