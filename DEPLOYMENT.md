# Deployment Runbook — going live on the quadrant rotation

Written 2026-08-21. Starting parameters: ~$11k initial capital (plus any
contributions accumulated before start), ~$1,500/mo contributions now,
ramping +20%/yr through the no-kids years then +7%/yr (workbook default;
anchored to user decade targets: >$5k/mo in the 30s, >$7k in the 40s,
>$10k in the 50s). The paper ledger keeps running regardless of the
live account — it is the benchmark the live account is measured against.

## Preconditions (before the first live order)

1. **The September 1 ledger row exists** — the Routine fires on the 1st
   and logs the month's quadrant + resolved per-tier allocations under
   matrix v7. Verify `paper/ledger.csv` gained a row.
2. **Tier chosen.** The workbook glide path defaults to VAGG at age 25.
   Entering one notch lower (AGG or MOD) and stepping up after the next
   regime turn is a legitimate use of the ladder; waiting in cash is the
   one option the data doesn't support (see PORTFOLIOS.md, mid-regime
   entry analysis).
3. **IBKR account settings, one time:**
   - Fractional shares: ON (whole-share replication mis-allocates ~1-1.5%
     at this account size; fractional → ~0).
   - Tax lot method: **Highest Cost** (HIFO) in the Tax Optimizer —
     worth ~0.1pp/yr, quantified in PORTFOLIOS.md.
   - No margin required: shorts are expressed via inverse ETFs (SCO/ERY)
     that appear directly in the resolved allocations.

## Day 1 (any business day after reading the current month's row)

1. Open the latest `paper/ledger.csv` row → `allocations` JSON → your
   tier's resolved weights. These are final — conditional duration, the
   momentum tilt, and the short book are already resolved into real
   tickers.
2. Dollar target per ticker = weight × account value. Fractional shares.
   The order calculator does the arithmetic from the latest ledger row:
   `python -m src.portfolio.order_calc --tier VAGG --equity <value>`
   (add `--held TICKER=DOLLARS` per position for monthly deploys — it
   applies contribution-first rebalancing and the 5pp drift band).
3. Buy with limit orders at or near the midpoint; there is no urgency —
   execution-day tests showed ±1pp noise between same-day and +10-day
   entry with no consistent direction. Spreading the initial buy over
   2-3 days is fine (tranching was validated); spreading over months is
   just underinvestment.
4. Time-of-day habit (free, worth single-digit bps/yr; PORTFOLIOS.md
   overnight study): execute equity-ETF buys near the CLOSE and equity
   sells near the OPEN (equity returns accrue overnight); bond-ETF
   trades the reverse (TLT accrues intraday). A convenience, not a
   requirement — never miss a rotation waiting for the right hour.

## Monthly routine (first week of each month, ~15 minutes)

1. The Routine logs the new month's row on the 1st. Read it.
2. **Regime unchanged** → do NOT sell anything. Invest the month's
   contribution into whatever is most underweight vs target
   (contribution-first rebalancing, adopted). Only if a position has
   drifted more than ~5 percentage points from target should a
   sell-to-rebalance happen (drift execution, adopted).
3. **Regime changed** → rotate: sell what leaves the book, buy the new
   book to target. HIFO lots. Expect the realized gains to be mostly
   short-term — that drag is already priced into every projection.
4. Opportunistic: harvest any lot more than ~5% underwater (sell,
   replace with the closest non-identical substitute or rebuy after the
   wash-sale window if the model still wants it).

## The short book, live

- Resolved allocations already contain the implementation: SCO (2x
  inverse oil) in Deflation cells, ERY (2x inverse energy equities) in
  Stagflation cells, each at half the sleeve weight beside a SHY
  remainder. Buy them like any other line item. No margin, no borrow.
- Global off switch: `INCLUDE_SHORTS = False` in
  `src/portfolio/matrix.py` reverts every cell to its long-only form
  from the next ledger run onward. CONS never holds shorts either way.
- Daily-reset inverse ETFs track a true short imperfectly over multi-week
  holds; this is disclosed, modeled, and acceptable at 5-7.5% position
  sizes. Do not substitute actual short sales on margin.

## What is NOT in scope

- The IBS options overlay and any biotech activity are separate sleeves
  with separate rules (see PORTFOLIOS.md / BIOTECH_CATALYST.md — the
  biotech deliverable is three avoidance rules, not a book).
- No intraday monitoring exists or is needed: every intra-month
  mechanism tested (crash brake, rebound accelerator) failed honest
  T+1 modeling. The system is monthly, complete, and quiet by design.

## Measuring yourself honestly

The paper ledger is the counterfactual. Once live, the only two
questions each quarter: (1) did the live account hold the ledger's
targets, and (2) how large is the execution gap (fills, fees, timing)
vs the ledger's mark-to-market? Everything else — regime calls, cell
performance — is the model's responsibility, already being graded by
the append-only ledger.
