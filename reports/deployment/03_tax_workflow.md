# Item 3 — Tax-lot accounting workflow

**Date:** 2026-05-03
**Branch:** claude/strategy-validation-v2
**Script:** `scripts/run_wash_sale_analyzer.py`
**Raw output:** `output_wash_sale.txt`

## Decision

**Use IBKR's default FIFO lot-matching with year-end consolidated 1099-B
as the primary tax record. Wash-sale handling is automatic (IBKR adjusts
basis on the broker side; reflected in 1099-B).**

Wash-sale risk for this strategy is **economically immaterial** despite
high volume:
- 82 wash sales over 26 years (~3/year)
- $18,262 of $22,442 total losses (81%) are wash-sale-affected
- BUT only $104 (1 trade) over 26 years actually crossed a tax year

99.4% of wash-sale dollars are same-year — the basis adjustment
recognizes the loss when the next exit closes, producing zero net tax
impact.

---

## How wash-sales work for this strategy (and why they don't matter)

### IRC §1091 mechanics

If you sell a security at a **loss** and buy a "substantially identical"
security within **30 days before OR after** the sale (a 61-day window
centered on the sale), the loss is **disallowed** for current-year tax
purposes. The disallowed loss is added to the cost basis of the
replacement shares.

The loss is not eliminated — it's deferred to whenever the replacement
shares eventually sell without another wash-sale trigger.

### How this strategy generates wash sales

QQQ exits during whipsaw periods (rapid signal flips) often:
1. Close the position at a small loss
2. Re-enter within 1-30 days when the signal flips back ON

Each such pair triggers the wash-sale rule. The historical analysis
shows this happens to 85% of loss trades.

### Why this is economically neutral in practice

Same-year wash sale:
- Day 1: sell QQQ for -$200 loss. Loss disallowed.
- Day 8: re-buy QQQ at $X. Basis = $X + $200 (disallowed loss added).
- Day 30: sell QQQ for +$300. Realized gain = $300 - $200 = $100.
- Net: $100 gain reported. Equivalent to $300 - $200 if no wash sale.

The deferred loss is fully recovered through basis adjustment in the
same tax year. No economic difference.

The ONLY case that matters is **tax-year-crossing**: a wash sale in
December that defers a loss into next year. This shifts the deduction
by one year (real but small impact).

### Historical analysis result

From `scripts/run_wash_sale_analyzer.py`:

| Metric | Value |
|---|---:|
| Total trades reconstructed (Conv 2) | 164 |
| Wins | 67 (avg $+595) |
| Losses | 97 (avg $-231) |
| Avg hold | 29 calendar days |
| Loss trades that are wash sales | 82 (85%) |
| Total realized losses | -$22,442 |
| Loss dollars affected by wash-sale | -$18,262 (81%) |
| **Tax-year-crossing wash sales** | **1 ($-104 over 26 years)** |
| Same-year wash sales | 81 |

The single tax-year-crossing wash sale (2011-12-13 → 2012-01-04) deferred
$104 of loss recognition by 17 days into the next tax year. That's a
trivial impact: at 24% STCG, a one-year deferral of $104 = ~$25 of
present-value loss in tax efficiency. Over 26 years.

### Whipsaw clusters (from output)

20 distinct periods with ≥2 wash sales within 90 days. Largest clusters:

- **2014-10-02 → 2015-06-30** (12 wash sales, total -$2,141): the 2014-15
  oil-shock chop period
- **2019-05-14 → 2019-10-08** (8 wash sales, -$1,144): trade-war whipsaws
- **2005-08-25 → 2006-05-02** (7 wash sales, -$1,180): late-cycle 2005-06 chop
- **2023-08-16 → 2023-10-19** (5 wash sales, -$1,335): 2023 banking-stress aftermath
- **2018-02-08 → 2018-04-23** (3 wash sales, -$1,351): vol-spike Q1 2018

All these are within calendar years. None defer losses to the next year.

---

## IBKR tax-lot operational mechanics

### Default lot-matching

IBKR default is **FIFO** (First In, First Out). The IRS permits two
methods: FIFO and Specific Identification. FIFO requires no per-trade
action.

### Why FIFO is fine for this strategy

The strategy always **sells 100% of the QQQ position** on each signal
flip. There are no partial sells. So lot-matching method is **moot** —
all lots go on every exit.

### When the user might consider Specific Identification

Only relevant if:
1. We started doing partial position management (currently no plan to)
2. We wanted to optimize tax-loss-harvesting across QQQ lots (currently no)

For the locked deployment spec, FIFO is the right choice.

### Tax Optimizer tool

IBKR provides a Tax Optimizer that lets the user:
- Change lot-matching method per-trade until 8:30 PM ET on trade day
- See unrealized gain/loss per lot before selling
- Switch to LIFO, Highest Cost, Lowest Cost, Maximize Long-Term Gain,
  etc.

For our use case, we won't be using this. The bot will just submit
MOC orders and rely on FIFO.

---

## Year-end tax workflow

### What IBKR provides

| Form | Content | Source |
|---|---|---|
| **1099-B (Consolidated)** | Every QQQ + SGOV trade, basis-adjusted for wash sales (Box 1g shows wash-sale-disallowed amounts) | IBKR Year-End Statements |
| **1099-DIV** | SGOV distributions (Box 1a, ordinary dividends, federally taxable) | IBKR Year-End Statements |
| **1099-INT** | T-bill interest if held directly (not applicable; we use SGOV ETF) | n/a |

### What the user (operator) needs to do

1. Wait for year-end 1099 (typically February-March)
2. Verify total trades on 1099-B match strategy log
3. Schedule D + Form 8949 for capital gains/losses
4. Schedule B for SGOV dividends
5. Keep the strategy log as backup documentation (entry/exit dates,
   prices, P&L per trade) — useful only if the IRS challenges the
   1099-B figures, which is rare

### What the bot's logging must capture

For audit trail purposes, the bot should log per trade:
- Trade ID (UUID)
- Symbol (QQQ or SGOV)
- Side (buy/sell)
- Submission timestamp (15:55 ET MOC submission)
- Fill timestamp (16:00 ET official close)
- Fill price
- Share count
- Trigger reason (signal flip details: SMA values, regime change)

The bot already supports this via the existing trade-log infrastructure.
No new code needed — just verify it's enabled.

---

## Specific tax considerations for Texas-resident taxable account

| Item | Treatment |
|---|---|
| QQQ short-term gains (held ≤1 year) | STCG, ordinary income rate (24% in user's bracket) |
| QQQ long-term gains (held >1 year) | Won't happen — strategy avg hold is 29 days |
| SGOV dividends | Treasury interest, federal ordinary income (24%) |
| State taxes | None (Texas) |
| Foreign tax credits | None (QQQ is US, SGOV is US Treasuries) |
| K-1 forms | None (neither QQQ nor SGOV is a partnership) |
| Wash-sale adjustments | Auto-handled by IBKR on 1099-B |

### Estimated annual tax events

At 12.58 transitions/yr, ~6 round trips/yr on the QQQ leg + ~12 SGOV
distributions/yr = **~18 reportable events/yr** on Schedule D and
Schedule B.

Total tax-prep complexity increase: minor. TurboTax / standard tax
software imports IBKR's 1099-B directly and handles wash-sale
adjustments automatically.

---

## Item 3 conclusion

**Tax workflow RESOLVED.**

| Item | Decision |
|---|---|
| Lot-matching method | FIFO (IBKR default) — moot since 100%-sell on each exit |
| Wash-sale handling | Automatic via IBKR 1099-B basis adjustments |
| Wash-sale economic impact | Effectively zero (only 1 tax-year-crossing in 26 years) |
| Record-keeping | Year-end 1099-B sufficient; bot logs as backup audit trail |
| Tax software workflow | Standard 1099-B import; no special handling required |

**Risk surface for the deployment:**
- The 1 in 26 years tax-year-crossing wash sale event = ~4% probability
  of one such event per year. Acceptable risk given the small dollar
  impact (~$100 deferred per occurrence).
- If the strategy whipsaws heavily in late December, the user can
  manually choose to NOT re-enter until January 2 to avoid wash-sale
  basis-shifting (a small operational override). Optional.

**Sources:**
- [IBKR Tax Lot Selection](https://www.ibkrguides.com/traderworkstation/about-tax-lot-selection.htm) — FIFO default, Specific Identification permitted
- [IBKR Lot Matching Methods](https://www.ibkrguides.com/traderworkstation/lot-matching-methods.htm)
- [IRC §1091 Wash-Sale Rule](https://www.law.cornell.edu/uscode/text/26/1091) — 30-day window, basis adjustment mechanics
