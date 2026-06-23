# QA Pass 01 — Deployment Stack Review

**Date:** 2026-06-23
**Scope:** `src/deploy/` (signal → store → daily_check → broker → orders →
portfolio → alerts → reconcile → reporting) and its test suite.
**Method:** Independent code review (subagent) + targeted reproduction scripts
that exercise the suspected failure path against `SimStockBroker` /
`Ledger` before and after each fix.

**Result:** 2 real bugs found and fixed (1 CRITICAL, 1 HIGH), each with a
dedicated regression test. 4 known limitations documented (deferred by
design, not defects). Full project suite green: **251 passed**.

---

## Bugs found and FIXED

### CRITICAL-1 — `plan_orders` sized OFF-vehicle (SGOV) sells against the *pooled* broker balance

**File:** `src/deploy/orders.py` (ENTER branch of `plan_orders`).

**Symptom.** On ENTER (OFF→ON) the planner computed the SGOV-to-sell from
`min(target_dollars, broker_total_SGOV)`. Broker positions are read **once**
before the loop and never decremented, so when two sleeves flip ON the same
day each sleeve sees the *entire* pooled SGOV balance.

**Reproduction.** NAV $10,000, broker holds 60 SGOV, both sleeves (QQQ 50% +
BTC 50%) flip ON. Each sleeve sized `min($5,000, $6,000) = $5,000 → 50 SGOV`.
Combined order: **100 SGOV sells against 60 held** → the second sell is
rejected by the broker, leaving that sleeve un-funded and the portfolio
mis-allocated. (The previously-passing symmetric test only worked because
`min()` happened to cap each sleeve at exactly half the pool.)

**Fix.** `plan_orders` now accepts an optional `ledger`. When supplied
(the orchestrator always supplies it), each sleeve sells **only the SGOV it
parked**, read from `Ledger.open_shares_by_strategy("SGOV")[strategy_id]`.
Per-sleeve sizing is the correct accounting model — entering means fully
liquidating that sleeve's own parked cash. Without a ledger the planner
falls back to the old pooled sizing (single-sleeve-only correct) and the
docstring says so explicitly.

New helper: `Ledger.open_shares_by_strategy(symbol)`.

**Regression tests** (`tests/deploy/test_orders.py`):
- `test_enter_sizes_sgov_per_sleeve_from_ledger` — two same-day flips, each
  sells its own 30 SGOV, combined 60 ≤ 60 held. ✅
- `test_enter_without_ledger_can_oversize_pooled_sgov` — pins the hazard:
  without a ledger the combined ask exceeds what's held. ✅

---

### HIGH-1 — Wash-sale basis addon disallowed the *entire* loss on a *partial* replacement

**File:** `src/deploy/portfolio.py` (`_maybe_flag_wash_sale`,
`_apply_pending_wash_sale`).

**Symptom.** Both methods computed
`per_share_addon = total_loss / replacement.original_quantity` and recorded
`wash_sale_disallowed_loss = total_loss`. That is only correct when the
replacement quantity equals the sold quantity. For a partial replacement it
(a) disallowed too much loss and (b) inflated the small replacement lot's
per-share basis.

**Reproduction.** Sell 100 QQQ at a $1,000 loss ($10/sh); buy back only 30
within the window. Old code disallowed the **full $1,000** (should be the
loss on the 30 replaced shares = **$300**) and bumped the 30-share lot's
basis by **$33.33/sh** (should be **$10/sh**).

**Fix.** Per IRC §1091, only the loss on `min(sold, repurchased)` shares is
disallowed:

```python
matched_shares = min(sale.quantity, replacement.original_quantity)
disallowed     = total_loss * (matched_shares / sale.quantity)
per_share_addon = disallowed / replacement.original_quantity
```

The total basis bump (`per_share_addon * lot.original_quantity`) now equals
the disallowed dollars, and the deductible portion of the loss on the
un-replaced shares is preserved.

**Regression tests** (`tests/deploy/test_portfolio.py`):
- `test_wash_sale_partial_replacement_disallows_only_replaced_shares` —
  sell 100, buy 30 → $300 disallowed, $10/sh addon. ✅
- `test_wash_sale_partial_replacement_pre_existing_lot` — the
  `_maybe_flag_wash_sale` (replacement bought *before* the sale) path. ✅

All pre-existing wash-sale tests use symmetric quantities (sell N / buy N)
and remain correct and green.

---

## Known limitations — documented, NOT defects

These are conscious scope boundaries surfaced during QA. None block Stage-1
operation; each has a clear activation trigger.

### KL-1 — Startup reconciliation is per-symbol, not per-sleeve
`reconcile_startup` aggregates ledger lots by symbol before comparing to the
broker, because the broker has no concept of sleeve attribution. Consequence:
if two sleeves' ledger attribution drifts but the **symbol totals** still
match the broker, reconciliation reports "safe." Internal sleeve-attribution
errors are caught instead by the per-sleeve P&L report drift column, not by
startup reconciliation. Acceptable: the broker total is the only thing that
can cause a *bad trade*, and that is checked exactly.

### KL-2 — No target-driven initial-positioning path
`plan_orders` reacts to **flips** (incremental ENTER/EXIT). There is no
"bring the portfolio from an arbitrary starting allocation to target weights"
routine. First-time funding and post-discrepancy re-basing are an
**orchestrator** responsibility (the `python -m src.deploy.run` entry point,
still to be built) and must be done deliberately, not inferred from a signal
change. Tracked for the orchestrator build.

### KL-3 — Wash-sale model is sleeve-scoped; IBKR 1099-B is authoritative
We track wash sales **within a strategy_id** and **only for QQQ shares**
(`_WASH_SALE_SYMBOLS`). Real IRS rules don't distinguish sleeves and can span
substantially-identical securities across accounts. Our ledger figure is a
**management/estimation aid**; the broker's year-end 1099-B is the
authoritative tax document and should be reconciled against at filing time.
This is by design (documented in `portfolio.py` and the tax workflow note).

### KL-4 — Futures vehicles (MNQ/MBT) intentionally unsupported in Stage 1
`resolve_risk_symbol` raises `NotImplementedError` for futures vehicle
codes. These activate only at the account-size thresholds in
`baskets.json` ($60k QQQ→MNQ, etc.) and require a separate futures order
path. Failing loudly (rather than silently mis-routing a futures code as a
stock) is the correct Stage-1 behavior.

### KL-5 — Overnight MOO fills bridged across runs — RESOLVED
*(Originally a known limitation; closed by `src/deploy/pending.py`.)*

`src/deploy/run.py` records FILLED tickets into the ledger immediately
after `execute_plans` / `execute_positioning` returns. For MKT that fills
synchronously inside the run. For MOO (the production order type) the fill
lands at the NEXT session's opening auction — hours after the orchestrator
returns — so the placing run cannot record it.

**Fix shipped.** `PendingOrderStore` atomically persists submitted-but-
unresolved orders (with their `strategy_id`, which the broker doesn't
track). `drain_pending` runs as **Step 0 of every run, BEFORE reconcile**:
it polls the broker for each pending order and
  - FILLED → records into the ledger as of the current trading date, drops
    from pending;
  - REJECTED/CANCELLED → drops, surfaced as a CRITICAL alert;
  - SUBMITTED → kept pending;
  - unknown to the broker → kept pending and surfaced (never silently lost).

Because the drain records overnight fills before reconcile compares ledger
vs broker, the previously-expected ORPHAN_POSITION halt no longer occurs.
Covered end-to-end by `test_moo_order_drained_next_run_before_reconcile`
(MOO placed day T, filled overnight, drained + recorded day T+1, reconcile
clean). This removes the last blocker for the IBKR paper-account dry-run.

---

## Test status after pass

| Suite | Result |
|-------|--------|
| `tests/deploy/` | 111 passed (107 prior + 4 new regression) |
| Full project (`pytest`) | 251 passed |

(The full suite required installing the already-declared `httpx` dependency,
absent from the fresh container; not a code issue.)
