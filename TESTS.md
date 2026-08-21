# Test Registry — everything tried, with verdicts

One line per idea. Full evidence lives in PORTFOLIOS.md (and CL1_USO_STRATEGY.md,
CL_SURGE_CALLS.md, BIOTECH_CATALYST.md). Verdict key: **YES** = adopted, in the
live matrix/process. **NO** = tested and rejected. **FILED** = validated or
promising but parked, with its reactivation condition. Updated 2026-08-21.

## Adopted — YES

| # | Idea | Evidence in one line |
|---|---|---|
| 1 | Four-quadrant regime classifier (SPY/DBC vs 10m SMA, ex-ante monthly) | trigger-robust across 9 switch variants; replicates on 1987-2006 |
| 2 | Monotonic tier ladder (MOD defines, CONS dilutes, AGG/VAGG add octane) | monotone in-regime returns in 7 of 8 era×quadrant cells out-of-sample |
| 3 | Trend-conditional duration in stagflation cells | +11.1%/+15.5% in S-months, both eras |
| 4 | Reflation commodity momentum tilt (45/32.5/22.5 by 6m momentum) | +0.2-0.4pp, risk flat, both tiers |
| 5 | Deflation gold 25-30% + small equity rebound slice | gold +25%/+31%/yr in D-months, both eras |
| 6 | SHY over rolled T-bills as the cash instrument | +0.35%/yr on the cash sleeve |
| 7 | Drift execution + contribution-first rebalancing | rebalancing cost cut, no signal cost |
| 8 | Short oil in Deflation (SCO half-weight), matrix v5 | USO −43%/yr modern D, GSCI negative pre-2007; regime is self-limiting |
| 9 | INCLUDE_SHORTS global switch + short registry | one flag reverts every short to long-only cells (tested exact) |
| 10 | Short energy equities in Stagflation (ERY half-weight), matrix v6 | −26.5%/−3.4% absolute both eras; underperforms market ~13pp/yr in S in both |
| 11 | Tax habits: HIFO lots, contributions buy underweights, harvest >5% losers | +1.6-2.3% terminal wealth, one-time setup |
| 12 | TMF kept unconditional in D-cells | convexity ballast: +0.2-0.4pp in-cell despite weak standalone sleeve |

## Rejected — NO

| # | Idea | Why it died |
|---|---|---|
| 1 | CL1/USO lead-lag arbitrage (the original idea) | fully arbitraged: 0.988 same-minute correlation, zero exploitable lag |
| 2 | Every intraday CL/USO variant (scalps, adds, gap-downs, crossings) | all negative long-run; hand-trading profits were regime beta |
| 3 | Vol targeting on the rotation | no improvement over fixed weights |
| 4 | Signal smoothing / hysteresis / confirmation delays | every delay variant destroys the crash exit that pays for the system |
| 5 | Slower rotation cadences (2-6 month) | monthly wins; the "whipsaw" flickers are load-bearing crash exits |
| 6 | Crash brake (intra-month SMA exit) | RETRACTED — entire benefit was a one-day look-ahead artifact |
| 7 | Rebound accelerator (intra-month re-entry) | bear-trap buyer: 48% false fires, catastrophic tails |
| 8 | Conditional duration in Deflation (S-cell symmetry) | D already IS the bond-friendly regime; filter subtracts |
| 9 | TLT-vs-IEF momentum selection in D | no effect |
| 10 | G-cell momentum selection (QQQ/SPY/EFA/EEM) | insurance not alpha: pays ex-US eras, costs QQQ eras (FILED with trigger, see below) |
| 11 | Short broad equity in stagflation | failed pre-2007 (+ market up +9.1%/yr there); banned by standing rule |
| 12 | Short bonds in stagflation | helped modern, hurt pre-2007 |
| 13 | Short semiconductors in stagflation | passed the screen, failed impact (edge thinner than borrow) |
| 14 | GDX for GLD in AGG/VAGG D-cells | user decision: pre-2007 leg can't distinguish miners from bullion |
| 15 | Early-cycle rebound basket (IYT/XRT/XLY) in D | +0.1pp, deeper CONS drawdown |
| 16 | Semis long in G-cell | beats QQQ both eras but same tech supercycle sampled twice |
| 17 | Biotech long in S-cell | textbook false passer: no pre-2007 relative alpha, n=19, neighbor contradicts |
| 18 | Any sub-sector long replacing an incumbent | XLE-in-R confirmed as the grid's own #1; nothing else survives |
| 19 | Crypto in the matrix | one macro cycle of history; equity-beta fingerprint, fails as hedge exactly when needed |
| 20 | Leverage timing by regime age (ramp-in / taper / boost) | the vol pattern that powers it inverts exactly across eras |
| 21 | Dynamic tier per regime ("risk basket by regime") | dominated by fixed tiers both eras — the cells already do the risk timing |
| 22 | Calendar-month seasonality | seasonal means correlate +0.18 across eras — noise |
| 23 | Carry-conditional TMF (curve-slope rule) | curve is steep in nearly all D-months both eras; rule never discriminates |
| 24 | Level-conditional TMF (rate threshold) | any threshold splits eras, not months — fitting with n≈2 |
| 25 | Momentum tilt in G (investable) | PDP lags QQQ by 6.6pp/yr in G-months; academic decile can't be packaged |
| 26 | Quality tilt in D (investable) | SPHQ lags SPY in D-months |
| 27 | Value tilt in R (investable) | survives modern wrapper (+2pp) but degrades the pre-2007 era via Windsor |
| 28 | Real estate, long or short | mediocre in every cell in both eras; fails both screens |
| 29 | Thematic baskets (13 screened) | tech themes = diluted QQQ beta losing full-period; narrative themes = negative 20-year CAGRs |
| 30 | Biotech catalyst run-up harvest (naive + scheduled versions) | ex-ante tradeable version = exactly 0.00%; three avoidance rules delivered instead |
| 31 | Static 33/33/33 TQQQ/GLD/TLT (and kin) | −51% DD with beta 1.0; 2022 breaks all three legs at once; superseded by rotation |

## Filed — validated or promising, waiting on a condition

| Idea | Reactivation condition |
|---|---|
| Trend-gated BTC satellite (≤5%, 10m SMA gate, spot ETF) | user decision; the file quantifies +4pp CAGR at zero DD cost in the one era that exists |
| G-cell momentum-select contingency | 12m pick ≠ QQQ for 3+ consecutive G-months → rerun on live data |
| TMF high-rate sensitivity | forward ledger shows D-cell TMF contribution negative in the high-rate era → drop costs only ~0.2-0.4pp |
| XLE-short-in-S sizing above 15% | more forward S-months in the ledger |
| Biotech long side (anticipated-catalyst run-up, +3.2% suggestive) | a free historical PDUFA-date source |
| IBS options overlay + CL surge calls (execution layer) | IB Gateway connection for options data/orders |
| Commodity trend-following portfolio (user's Variant 1 on 13 futures) | roll-gap-clean continuous futures series (Yahoo splices are contaminated, esp. NG) |

## Interesting and NOT yet tested

Ranked by (two-era testability × mechanism strength × implementability):

1. **High-yield credit as sleeve and/or signal** — Vanguard High-Yield (VWEHX) runs daily to 1978, so a REAL two-era test exists. Does HY earn a seat in G/R cells? Does the credit spread confirm/lead the equity trend signal? Canonical macro literature says credit leads equities at turns.
2. **Dollar overlay for stagflation** — UUP earned +7.3% in modern S-months (screened once, no pre-2007 leg run); DXY index history reaches the 1970s, making the two-era test possible. A strong-dollar S-cell asset would be the first non-cash, non-duration long that works there.
3. **Commodity trend-following (the filed backtest, done properly)** — the canonical 2022-style stagflation performer; needs clean continuous futures (paid data or careful splicing). Highest expected value of anything on this list per the managed-futures literature.
4. **International/EM sleeves by regime** — proxies already in hand (VWIGX 1985, FEMKX 1990, EFA/EEM modern). Does ex-US equity earn a seat in R (weak-dollar regimes) that the commodity legs don't already cover?
5. **Gold trend-conditioning in D** — gold spot history to the 1970s; does a 10m SMA gate on the 30% gold slice help, or is D-gold like D-duration (always on)? Cheap test, symmetric to work already done.
6. **Regime-transition conditioning** — does the playbook for a G-month differ by predecessor (D→G rebound vs S→G resolution)? Two-era testable; state-splitting cuts sample size, so gate hard.
7. **TIPS in R/S** — mechanism is obvious but TIP only starts 2003; the pre-2007 leg needs synthetic real-yield construction. Flagged as data-limited before starting.
8. **Withdrawal-phase design** — not a backtest but a modeling gap: the glide path ends at CONS; the decumulation rules (sequence-of-returns, which sleeve to draw from by regime) are unwritten. Relevant in ~25 years, cheap to spec early.
