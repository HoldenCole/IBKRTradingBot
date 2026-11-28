# A levered-fund trend sleeve as an option beside VAGG: pre-registration (entry 120)

Written 2026-11-28 before any combined result below was computed. Nothing below may change after results are seen.

User direction: look at adding entry 119's trend rule as an option under VAGG.

## Design-rule conflict, stated first

The matrix's locked design rule (PORTFOLIOS.md, v2): AGG and VAGG own the same regime exposures as MOD with more
octane; no tier may own a regime asset the baseline does not. A trend sleeve across 17 sector, country and bond 3x
funds breaks that rule if put inside the cells. It is therefore tested only as a **satellite**: a fixed share of the
VAGG account, rebalanced monthly, running its own rule beside the unchanged v9 VAGG matrix. Whether to allow a
satellite at all is the investor's decision; nothing here changes the matrix or the ledger.

## Sleeves (entry 119, unchanged)

- **T17**: equal-weight trend rule on 17 synthetic 3x funds (SPY, QQQ, IWM, XLK, SMH, XLF, XLE, XLV, XLU, IYR, EEM, TLT,
  GDX, XBI, KRE, XHB, FXI): each held at 1/k of the sleeve (k = eligible funds) in months after a month-end close above
  its 10-month average, otherwise cash; 9 bp a side.
- **T1**: SPY at 3x in months after a month-end close above its 10-month average, otherwise cash.

## Variants

- V0: VAGG v9 alone (must reproduce the official engine numbers for the same window).
- V1: 80% VAGG + 20% T17. V2: 70% VAGG + 30% T17. V3: 80% VAGG + 20% T1.

Mixed monthly: the two parts are reset to their target shares at each month-end and drift within the month; the
cost of that monthly rebalance is ignored (stated as a small optimistic bias).

## Eras

- Modern: the official engine window (January 2007 onward), VAGG from `research/engine.py`.
- Earlier: January 2000 to December 2006, VAGG from `research/engine_pre2007.py`; T17 uses whichever of its 17 ETFs
  were eligible then (each 12 months after its first price).

## Pass

A variant passes if, in both eras, its CAGR and its Sortino (CAGR over downside deviation) are higher than VAGG
alone and its maximum drawdown is no more than 2 points worse. Also reported: the sleeve's correlation with VAGG,
both parts' returns by regime, and the account size at which T17 is practical (17 positions at IBKR minimums).
A pass makes the variant a candidate for the investor, nothing more.
