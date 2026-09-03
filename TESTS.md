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
| 13 | Washout-conditional D rebound slice (matrix v7, MOD/AGG/VAGG) | breadth <25% in defensive months → +1.4pp/+0.6pp better next month both eras; +0.3-0.6pp CAGR all tiers both eras; CONS excluded (mandate) |

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
| LEAPS as the G-cell leverage engine (deep-ITM ~50% moneyness, 1.9x, defined loss) | account ~$150k+ — today one contract ($13-38k) exceeds the whole account; financing only matches ETFs at low leverage; live-quote analysis in PORTFOLIOS.md |
| Managed-futures ETF (DBMF/KMLM) as S-cell instrument | outperform the S-cell allocation over the next ≥4 LIVE S-classified ledger months → test a 10-15% S-cell sleeve |

## Interesting and NOT yet tested

*(emptied 2026-08-21 — all eight ideas below were tested in the final-frontier sweep; results moved to the Rejected table and PORTFOLIOS.md. New ideas land here.)*

| # | Idea (tested in sweep) | Verdict one-liner |
|---|---|---|
| 32 | HY credit as sleeve | NO — beats no incumbent in both eras (D leg flips) |
| 33 | HY credit as early-warning signal | NO — warning direction itself flips between eras |
| 34 | Dollar overlay in stagflation | NO — +8.0%/yr modern S vs −7.8%/yr pre-2007 S; the 2022 dollar surge in costume |
| 35 | International/EM sleeves by regime | NO — never beats Nasdaq incumbent; EM −35%/yr modern S |
| 36 | TIPS in R/S | NO — fails on modern evidence alone; data gap never binding |
| 37 | Gold trend-gate in D | NO — and strengthens the cell: below-SMA D-months are gold's BEST both eras (crash V-bottoms); unconditional D-gold validated by its own conditioning failing |
| 38 | Regime-transition conditioning | NO — no (prev→next) pair deviates stably from base rates in both eras |
| 39 | Commodity trend basket | NO — all its edge is in R (already owned), −13.7%/yr in S, pre-2007 leg shows no edge; in-matrix trend-gating DBC is structurally a no-op |
| 40 | Withdrawal-phase design | SPEC WRITTEN (PORTFOLIOS.md) — dormant by design until ~age 60; rules pre-registered, sequence-risk test deferred |
| 41 | CCC/deep-junk spread stress as early warning | NO — third credit-canary failure; pre-2007 "stress" months were BETTER for equities (+1.61 vs +0.77%/mo) |
| 42 | BOJ assets → Nasdaq | NO — inverse in 1998-2011 (corr −0.20, reactive expansion), zero in 2012-2026, narrative corr −0.03 |
| 43 | Yen strength / carry-unwind warning | NO — backwards both halves (yen-strong precedes BETTER equity months); surge version flips sign across halves |
| 44 | CCC blowout → USMV rotation | FACT CONFIRMED (contemporaneous corr +0.60 real OAS) but NOT tradable — no predictive edge in any era; a hedging identity, not a signal |
| 45 | VIX term structure (backwardation warning) | NO — backwards (inversion precedes BETTER months, capitulation marker); as overlay it fires ~4x/decade, simultaneous with trend breaks; steep-contango complacency pattern is one-era-only by data birth |
| 53 | "Quadrant balances" breadth phase-clock (user's prior-job tool) | Q3 slow-top signature CONFIRMED both eras (weakest phase, but still positive → untradable); falling-phase strength = capitulation, already in v7 washout; phase choice inside S/D flips eras; age counter needs weekly data → intra-month graveyard. No change |
| 54 | Quadrant balances, member-level "main version" | %Q4-share is the best bottom discriminator measured (S/D spreads +1.3/+1.2pp both eras; weekly-fed +1.6pp) but portfolio-incremental over the v7 washout tilt ≈ 0 — extra months land in S (no equity tilt by design) or overlap washout in D. FILED with revisit trigger |
| 55 | Quadrant balances on the actual S&P 500 (499 members) | sharpest bottom diagnostic measured (S/D spreads +1.45/+1.91pp both eras) yet swapping/OR-ing it into the v7 tilt is neutral-to-worse — overlaps washout in D-months, extra edge lives where the tilt cannot act. Canonized as dashboard, not lever |
| 56 | LEAPS as leverage engine | FILED — one contract exceeds the account; financing only ties ETFs at 1.9x; revisit ~$150k |
| 57 | Levered sector ETFs beyond ERX (incl. 2x gold in D) | NO — leverage can't rescue rejected exposures; UGL-in-D is evidence-equivalent to the rejected GDX swap |
| 58 | Faster/asymmetric entry SMAs | REVISED → SHADOW: user's structural challenge validated by the trend test (edge positive in all 4 modern windows incl. both grinds, negative in both pre-2007 decades); running as informational shadow classifier in the ledger; promoted only if it wins the majority of live disagreements |
| 59 | Other metals (silver, copper, platinum, palladium) | NO on modern evidence — none beats GLD at its job; silver −34%/yr in S |
| 60 | Agricultural commodities (DBA, grains) | NO on modern evidence — ags underperform DBC in Reflation itself |
| 61 | Blue-chip dip-buying (UNH/BA style) | DATA-BLOCKED — survivor-sample +1.1-2.2%/mo excess is an upper bound manufactured by the bias; needs delisting-inclusive data |
| 62 | Regime-conditional cash (BIL in S) | NO — era inversion (2y duration beat bills +7.4/+2.8 in pre-2007 S); SHY stays; interest-bearing cash was already adopted design |
| 63 | Overnight vs intraday decomposition | Anomaly REAL and split-half stable (equities accrue overnight, bonds intraday); untradable as a strategy (252 RT/yr costs); ADOPTED as free execution habit — equity buys near close/sells near open, bonds reversed |
| 64 | Daily overnight-QQQ/intraday-TLT rotation | NO — gross +15.1% doesn't even beat QQQ B&H (+15.9%); each 0.5bp/side costs ~5.5pp/yr at ~1,000 trades; generalized: daily rotation is structurally unavailable to a taxable retail account |
| 65 | Strategy-ETF shelf (18 funds: managed futures, tactical, covered call, parity, buffer) | NO fund beats MOD in its own window on any metric; PHDG (closest concept) earns a third of ours; NSPY (overnight ETF) liquidated within a year. ONE find: KMLM/DBMF in 2022 S-months (+20.8/+14.1%/yr, n=9) — FILED as S-cell instrument candidate, trigger = outperform the S-cell over next ≥4 live S-months |
| 66 | Pitched NDX top-10 momentum model (screenshot) | NO — replication on the same survivor-deck BEATS the pitch (+26.1% vs 19.4%), exposing the ranking as a survivorship amplifier; real-world version (PDP) lags QQQ; even at face value dominated by the ladder (−47% DD at 19.4% vs VAGG's 32.4%) |
| 67 | Screener checkpoint frequency (daily / 2-3x-wk / weekly / biweekly vs monthly) | NO to everything faster than monthly — same rule checked more often loses in BOTH eras: full v7 books (modern) monthly beats weekly by 0.8pp (MOD) / 2.3pp (VAGG) with equal-or-better Sortino, daily costs 2-4.5pp at 16 flips + 28-32x turnover/yr; growth-boundary switch pre-2007 confirms (daily 9.9% vs monthly 14.1%). Weekly's only virtue (shallower boundary-switch DDs both eras) dies in the full book. Monthly evaluation IS the debounce filter |
| 68 | Entry-at-extension (is buying the already-up book worse?) | NO penalty that survives both eras. Modern R-months (n=108): 1-6m forward VAGG identical extended vs calm (6m +12.3 vs +12.5%, hit 80/81%); a 12m fade exists modern (+21 vs +26) but ERA-FLIPS — pre-2007 extended growth-on months did BETTER forward (12m +19.0 vs +13.0, 97% hit). Extension is momentum, and momentum was already validated. Soft flag: DBC extension 81st pctile today, its modern 12m stats weakest (+11.9%, 59% hit), commodity side un-era-checkable; the system's structural answer is the rotation itself |
| 46 | Valuation (CAPE) as a bottom signal | NO — cheap gets cheaper: modern extreme-cheap S/D months averaged −0.28%/mo through the GFC; even long-horizon CAPE flips eras |
| 47 | Financials as leading indicator | NO — exact era inversion (weak financials preceded rebounds pre-2007, healthy financials modern); monthly lead-lag corr ~0 both directions |
| 48 | Breadth washout as bottom signal | **ADOPTED as matrix v7** — see Adopted table #13 |
| 49 | Breadth thrust | NO — never fires while still classified defensive; the regime flips first |
| 50 | Vol-crest-passed as bottom signal | NO — exact era inversion (same vol flip as leverage timing) |
| 51 | Crash-month mean reversion | NO — crashes beget crashes mildly, both eras |
| 52 | Fed easing / credit turn inside S/D | NO as buy signals — both consistently NEGATIVE both eras (cuts confirm recessions; junk rallies in defensive regimes are bear rallies); recorded as real inverse findings, no action (book already defensive) |
