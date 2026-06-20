# Commodity Trend — Data Spike Findings

**Date:** 2026-06-20
**Branch:** claude/commodity-trend-research (off strategy-validation-v2)
**Budget:** half-day
**Purpose:** resolve Path A / Path B / Path C / Norgate-pay question before
committing to the 3-week build.

## Headline recommendation

**Pay for Norgate Data.** USD 148.50 for 6 months (or USD 270 for 12). This
is below the cost of further dev time on free-source workarounds, eliminates
the data-quality risk that was the project's single biggest unknown, and
delivers exactly what the spec requires for all 13 instruments.

Path A (clean free data, ≥11 of 13 instruments) **fails**:
- The Yahoo `=F` continuous series we already have are unadjusted —
  unusable as established in the scoping report (corn rolls every July,
  CL has a −306% phantom return in 2020, NatGas has 5.6% of days with
  >7% moves clustered at month-end).
- The most-cited free back-adjusted source (Nasdaq Data Link CHRIS / SCF)
  was **deprecated, with no replacement**. Even if accessible, the data
  is frozen.
- Stooq (next-most-cited free back-adjusted continuous host) is
  **hard-blocked from this remote execution environment** (immediate 503
  even with browser User-Agent and inter-request delays). It would likely
  work from your local machine, but the data-quality verification I was
  supposed to do in the spike I could not complete from this container.
- AlphaVantage: free tier is 25 req/day and only offers commodity **spot**
  prices, not futures. Not applicable.

Path D (commodity ETF proxies — USO/UNG/GLD/CORN/etc.) was not in the
original spec but is mentioned below as a fallback option.

## What I tested

### 1. Norgate Data — pricing and coverage (Path: paid)

Confirmed via the [Norgate Futures Package page](https://norgatedata.com/futurespackage.php):

| Tier | Price |
|---|---|
| 6 months | **USD 148.50** |
| 12 months | **USD 270** (~USD 22.50/month) |

Coverage:
- **~100 futures markets across 11 worldwide exchanges**
- **Historical data back to ~1980 or first day of trading**
- Provides **both unadjusted and back-adjusted** spot-month continuous
  contracts in two formats
- Close prices are **official exchange settlements**

This exceeds our 13-instrument basket by ~8× and our 26-year window by
~20 years. Settlement-based closes is exactly what your Q4 (execution
convention) requires.

Source: [norgatedata.com/futurespackage.php](https://norgatedata.com/futurespackage.php)

### 2. Yahoo `=F` continuous (free, already tested in scoping)

13 of 13 instruments fetch. All 13 are **unadjusted front-month**, with
documented roll gaps:

- Corn (`ZC=F`) top 5 daily moves: all in mid-July (old-crop / new-crop roll)
- NatGas (`NG=F`): 5.6% of days >7%, clustered at month-end
- WTI (`CL=F`): −306% phantom return on 2020-04-20 (negative-price episode);
  unrecoverable in a `pct_change` equity curve

**Not usable as the primary source.** Could be used to back-adjust ourselves
if we had per-contract data, but Yahoo doesn't ship per-contract data either
(only front-month continuous), so this isn't actually a path.

### 3. Stooq (free, Path A primary candidate)

Tested 5 instruments (CL.F, GC.F, NG.F, ZC.F, KC.F) with browser User-Agent
and 3-second inter-request delays. **All returned HTTP 503 immediately** —
this is an IP-level block from the remote execution environment, not a
transient rate limit.

I cannot verify Stooq's data quality from here. You may be able to test
from your local machine. Even if it works, we'd still need to verify:
- Coverage of all 13 across 2000-2026
- Whether it's back-adjusted (Stooq's documentation is unclear)
- Behavior across the 2020 WTI sign-change
- Roll-gap cleanliness on grain-rotation months

### 4. Nasdaq Data Link / Quandl CHRIS + SCF (free, was the leading free option)

Tested 5 CHRIS endpoints and 3 SCF endpoints via the documented v3 API
with a public demo key. **All returned HTTP 403** — same IP-block pattern
as Stooq (Akamai-style WAF block page).

**More importantly: web research confirms the CHRIS database has been
deprecated, with no replacement data feed available.** Quoting the search
finding: *"The CHRIS database has been deprecated and is no longer updated
on Nasdaq Data Link. However... there was no alternate data feed currently
available."*

So even with local IP access, CHRIS would deliver stale data — last updated
whenever the freeze took effect (reportedly 2022).

Source: [GitHub issue documenting CHRIS deprecation](https://github.com/PacktPublishing/Python-for-Algorithmic-Trading-Cookbook/issues/5)

### 5. AlphaVantage (free, limited)

Web research only (didn't burn a request). Free tier: 25 req/day. Coverage:
WTI, Brent, NatGas, Gold, Silver, Copper, Wheat, Corn, Sugar, Coffee, Cotton,
Aluminum. **All commodity SPOT prices, not futures.** Misses HO, RB, HG-as-
futures. Spot prices don't capture the roll-yield that futures trend
strategies are economically exposed to, so they'd answer the wrong question
for our spec.

### 6. Other paid options (mentioned for completeness)

- **FirstRate Data**: 130 futures back to 2007 (loses 2000-2007), one-time
  purchase model rather than subscription
- **Kibot**: 82 futures with per-contract data; we'd need to back-adjust
  ourselves (Q2 says difference/Panama)
- **Portara**: full back-adjusted continuous, all sectors; pricing on
  request (likely higher than Norgate)
- **Databento**: CME + ICE coverage with rollovers handled; pricing per
  market — generally higher than Norgate for full basket
- **EOD Historical Data**: ~USD 20/month, continuous futures included

Norgate remains the best fit at USD 22.50/month for the scope we need.

## Decision-tree result given findings

Per the locked decision tree:

| Coverage of 13 from free clean data | Decision |
|---|---|
| ≥11 of 13 ✓ | Proceed with Path A (3 weeks) |
| 8–10 of 13 | Proceed with reduced basket |
| <8 of 13 | **Decision point on paid data** |

We're at **0 of 13** clean from this environment. Even granting that
Stooq/Nasdaq might work from your local machine, CHRIS is deprecated and
Stooq's data-quality is unverified. The honest answer is: **<8 of 13**,
i.e., decision point on paid data.

## Three paths forward

### Path A.norgate (RECOMMENDED): Buy Norgate, proceed as planned

| | |
|---|---|
| Cost | USD 148.50 (6 mo) or USD 270 (12 mo) |
| Coverage | All 13 instruments, 1980-present, settlement-based |
| Data quality | Verified by Norgate; widely used in retail-quant community |
| Methodology fit | Both unadjusted and back-adjusted; we apply Q2 (Panama difference) to our preferred series |
| Timeline impact | Same as scoped: ~3 weeks total |
| Risk | Subscription expiry mid-project (mitigated by 12-month plan) |
| Total project budget | Norgate + dev time; you already approved 3 weeks. The $148.50–$270 is a rounding error. |

### Path A.local (cheap, slower, uncertain): Test Stooq from your local machine

| | |
|---|---|
| Cost | $0 |
| Coverage | Unknown — needs you to verify |
| Risk | Stooq quality not confirmed; even if good, requires us to build a sync pipeline from your local machine to the dev environment, OR you fetch and check in CSVs |
| Timeline impact | +2-3 days to verify quality + build local-fetch workflow; could go longer if quality issues surface |
| Recommendation | Worth a half-hour test from your end if you want to avoid Norgate, but you'd want to verify quality with the same tests we ran on Yahoo (corn July rolls, CL 2020 sign change, NatGas month-end gaps) |

### Path D (deviation from spec): Commodity ETF proxies

Not in the original spec but worth flagging as the cheapest possible path.
ETF proxies available via Yahoo with full dividend-adjusted history:

| Spec instrument | ETF proxy | Inception | Notes |
|---|---|---|---|
| CL (WTI) | USO | 2006 | Documented contango drag |
| BZ (Brent) | BNO | 2010 | |
| NG (NatGas) | UNG | 2007 | Severe contango drag |
| HO (heating oil) | — | — | **No clean ETF (UHN discontinued)** |
| RB (RBOB) | — | — | **No clean ETF (UGA discontinued)** |
| GC (gold) | GLD or IAU | 2004 | Clean |
| SI (silver) | SLV | 2006 | Clean |
| HG (copper) | CPER | 2011 | |
| ZC (corn) | CORN | 2010 | |
| ZS (soybeans) | SOYB | 2011 | |
| ZW (wheat) | WEAT | 2011 | |
| SB (sugar) | CANE | 2011 | |
| KC (coffee) | JO | 2008 | |

**Pros:**
- Free, immediate, dividend-adjusted (no roll-gap problem)
- Answers a deployment-realistic question: "what would a retail trader
  actually realize in trend-following on commodity exposure?"
- ETF expense ratios and contango drag are already baked in

**Cons:**
- Misses 2 of 13 instruments (HO, RB)
- ETF inceptions are mostly 2008-2011, so the 2000-2009 sub-period is
  largely empty for most names → loses the critical regime-shift test
- ETF tracking error means trend signals fire on ETF price, not commodity
  price — this is a different question than the spec asks
- Deviates from the locked spec wording ("trend strategies on commodity
  futures")

**Verdict:** Not a substitute for Path A.norgate. Could be a useful
sanity check or a "Phase 0" preliminary backtest while waiting for Norgate
to deliver, but not a full answer to the spec.

## Methodology questions resurfacing

Two methodological consequences of paying for data that are worth noting:

1. **Back-adjustment methodology can be verified, not just assumed.** Norgate
   provides BOTH unadjusted and back-adjusted series. We apply Q2 (Panama
   difference) to the unadjusted series and **cross-check** against Norgate's
   own back-adjusted series. Any divergence flags a methodology problem
   we caught at construction rather than at backtest-result time.

2. **The CL 2020 negative-price episode** is in any honest history. Norgate's
   back-adjusted handling is documented (they keep it as a real event). Our
   own Panama implementation will need to either:
   (a) Skip the affected window in vol calculations (event filter)
   (b) Apply the difference adjustment carefully (subtract negative settlement
       difference even though it sign-flips)
   I'd default to (b) with explicit logging of the event date, since
   skipping introduces selection bias. Confirm before implementation.

## Engineering effort estimate — revised

Holding the Path A.norgate scenario:

| Component | Effort | Change from scoping |
|---|---|---|
| Norgate setup + auth + cache + sync | 1 day | new (replaces "find clean source") |
| Per-instrument data validation (settlement vs back-adjusted check, gap detection) | 1 day | new (now possible because we have settlements) |
| Panama back-adjustment implementation + cross-check against Norgate's | 1 day | new sub-task |
| 60-day realized vol module | 0.5 day | unchanged |
| **Full-covariance vol-targeting module** (per Q1) | 1.5 day | upgraded from 0.5 day independent-vol |
| Multi-position book manager (13 positions, daily rebalance, 25% cap, T-bill idle) | 2-3 days | unchanged |
| Signal 1: SMA 50/200 | 0.5 day | unchanged |
| Signal 2: Donchian 100/50 asymmetric | 0.5 day | unchanged |
| Signal 3: vol-adj momentum (12m ret/vol, top-50% of 24m range) | 1 day | unchanged |
| Roll-cost model (per-sector schedules + bid-ask) | 1-2 days | unchanged |
| Portfolio vol-targeting backtest engine | 2-3 days | unchanged |
| Reporting: per-sector attribution, correlation matrices, sub-periods, **revised Tier A/B/C/D bars** (per Q3) | 2-3 days | unchanged |
| Comparative analysis + writeup (×3 variants) | 2-3 days | unchanged |
| **Total** | **~3.5 weeks** | +0.5 week from scoping (Norgate setup + Panama cross-check + full-cov vol-targeting upgrade) |

Still under your 6-week red line. The extra half-week buys us a much
stronger data foundation and the full-covariance vol-targeting you
specifically called for.

## What I need from you before proceeding

Two confirmations:

1. **Confirm Norgate purchase.** USD 148.50 (6 mo) or USD 270 (12 mo).
   You'd buy the subscription and provide credentials (or download CSVs
   we sync into the dev environment). I'd recommend the 12-month plan
   given the 3.5-week build + some buffer for paper/refinement.

2. **Confirm CL 2020 negative-price handling.** I lean toward "apply
   difference adjustment carefully with explicit logging of the date"
   (option b above) rather than skipping. Confirm or specify.

## What I have NOT done

Per the spec's gate ("Don't proceed past the spike without confirmation"):

- No backtest code written.
- No signal modules implemented.
- No commodity data downloaded into the repo (the Yahoo testing was on
  `/tmp` only).
- No commitments to long-running data subscriptions on your behalf.

The only thing committed is this spike report.

## Sources

- [Norgate Futures Package pricing](https://norgatedata.com/futurespackage.php)
- [GitHub issue confirming CHRIS deprecation](https://github.com/PacktPublishing/Python-for-Algorithmic-Trading-Cookbook/issues/5)
- [AlphaVantage commodities endpoint documentation (general reference)](https://www.alphavantage.co/documentation/)
- [Original spec: `New Trading Strats` on main branch](https://github.com/HoldenCole/IBKRTradingBot/blob/main/New%20Trading%20Strats)
