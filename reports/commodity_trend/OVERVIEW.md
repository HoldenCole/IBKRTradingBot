# Commodity Trend Research — Data & Strategy Breakdown (First Run)

**Date:** 2026-06-21
**Branch:** claude/commodity-trend-research
**Status:** First-round research complete; framework reusable; commodity
trend treated as a separable problem from the locked equity strategy.

---

This document is the consolidated reference for what was actually tested,
what we learned, and what a *second* run would look like. The commodity
problem is structurally different from the equity problem we solved
earlier, and the framing here is "first pass, not final word."

## 1. Why commodities are not equities (and why this matters)

The equity strategy works because broad equity indices have a strong
upward drift and most of the variance is on the downside. SMA(50)/(200)
on QQQ effectively asks "is the long-term drift still in force?" and gets
the answer right ~70% of the time across 98 years.

Commodities do not work this way:

- **No structural drift.** Real commodity prices are roughly flat over
  multi-decade horizons (with cyclical episodes). There is no equivalent of
  "the secular bull market" to fall back on. A trend filter has to *find*
  trends; it can't *assume* them.
- **Carry and roll yield are first-order.** Commodity futures returns
  decompose into (spot move + roll yield). For some instruments (NG in
  contango, GC in long-stretches of contango) roll yield dominates the spot
  move. Equity futures don't have this — they're priced off interest rates
  and dividends, both small.
- **Cross-sectional dispersion is huge.** Energy, metals, grains, and
  softs barely correlate. A signal that works on gold may say nothing
  about wheat. The equity strategy has one signal on one instrument; the
  commodity problem has *N* signals on *N* uncorrelated instruments and
  has to compose them into a portfolio.
- **Bear regimes are different.** Equity bears are usually short and
  sharp (months); commodity bears can be a decade long and grinding
  (2011-2020). A trend signal that protects in equity bears can be
  ground to pieces in a commodity bear.
- **Roll mechanics introduce data artifacts** that don't exist in cash
  equities: contract expiry, calendar gaps, contango/backwardation
  changes, and the negative-price episode (CL April 2020). Half the data
  work on this round was about handling these correctly.

These structural differences are why this round is best viewed as a
first run. Lessons from equities don't all transfer.

---

## 2. The data — what we tested on, what we missed

### 2.1 Target universe (per spec)

13 instruments across 6 sectors:

| Sector | Instruments | Exchange |
|---|---|---|
| Energy | CL, BZ, NG, HO, RB | NYMEX (CME) + ICE Europe |
| Precious metals | GC, SI | COMEX (CME) |
| Industrial metals | HG | COMEX (CME) |
| Grains | ZC, ZS, ZW | CBOT (CME) |
| Softs | SB, KC | ICE US |

### 2.2 What we actually got

| | Tested | Missing |
|---|---|---|
| Universe | **10 of 13** CME-listed instruments | **3 ICE** instruments: Brent (BZ), Sugar (SB), Coffee (KC) |
| Period | **2010-06 → 2026-06** (~16 yrs) | **2000-2009** sub-period (~10 yrs) |

### 2.3 The data-source decision

The spike round tested every viable free source for back-adjusted
continuous commodity futures:

| Source | Result |
|---|---|
| Yahoo `=F` | Unadjusted only; corn rolls every July, CL has a −306% phantom return in 2020 — unusable as-is |
| Stooq | IP-blocked from this remote container |
| Nasdaq Data Link / CHRIS | Deprecated and frozen as of ~2022 |
| AlphaVantage | Free tier 25 req/day, spot only, no futures |
| EODHD | No clean continuous futures product |
| FirstRate | One-time purchase but only back to ~2007 |
| CSI Data | Norgate's wholesaler; comparable price, clunkier UI |
| **Databento** (chosen) | **API works; 10 CME free-ish ($0.36-$2 one-time); ICE is an extra paid licensing tier; pre-2010 data not available** |
| **Norgate** (attempted) | Trial hard-capped at 2 years; **paid $270/yr would unlock full 1980-present**; not pursued |

Decision: Hybrid plan — Databento for the 10 CME instruments where it
worked, Norgate for the 2000-2009 backfill + ICE trio. The Databento half
shipped clean; the Norgate half was blocked by the trial cap and the user
elected not to spend $270 for a nice-to-have.

### 2.4 Data quality work (what made the difference)

Four real issues were caught during data prep that would have silently
corrupted results:

1. **CME Sunday-evening sessions.** Databento's `ohlcv-1d` buckets by UTC
   calendar day, so the Sunday-evening electronic session (part of
   Monday's CME trade date) appeared as a separate, tiny-volume Sunday bar
   — inflating the calendar to ~310 bars/yr and creating partial-session
   bars. Fixed by `collapse_to_trade_date()` (reassign Sunday → Monday,
   aggregate OHLCV).

2. **Calendar vs volume roll.** Initial calendar-roll (`.c.0`) landed on
   illiquid metal contract months (silver concentrates in Mar/May/Jul/
   Sep/Dec) that don't trade daily — silver lost ~30% of sessions.
   Switched to volume-roll (`.v.0`), which follows the most-liquid
   contract and is the standard CTA convention. Side benefit: volume-roll
   sidesteps the CL April 2020 negative-price blowup entirely (volume had
   already rolled off the expiring May contract).

3. **Panama back-adjustment.** Raw continuous still contains roll gaps
   (corn dropping 24% on a July roll, etc.). Implemented difference
   (Panama) adjustment using the second-month series to isolate each
   roll's gap. Anchored to present (latest close unchanged), cumulative
   gaps subtracted backward through history. 1,276 total rolls cleanly
   removed. Spot-checked correct on individual roll days (e.g., what
   looked like a +1.27% CL day in raw was actually a −3.33% day after
   the contract switch is properly accounted for).

4. **Grain calendar-NaN signal zeroing.** The panel uses a union calendar
   across instruments, so grains had NaN rows on ~240 days/yr when energy
   trades and they don't. `rolling(window, min_periods=window)` on the
   union frame made any window containing those NaNs evaluate to NaN →
   False, silently zeroing grain V1/V2 signals (ZC showed 0% ON; correct
   is 19%). Fixed by computing each signal per-instrument on its own
   valid series, reindexed and forward-filled.

---

## 3. The strategies — three signal variants

All three are **long-flat** (ON = hold long, OFF = capital → T-bills),
applied independently per instrument, composed into a vol-targeted book.

### 3.1 V1 — Classic 50/200 SMA crossover

**Definition:** `ON when close > SMA(50) AND SMA(50) > SMA(200)`

**What it's trying to catch:** The same regime that the equity strategy
uses. Long-term up-trend, confirmed by both a fast and a slow moving
average, with price still above the fast one.

**Why test it first:** Direct generalization of the proven equity
strategy. If commodity trend "just works" like equity trend, V1 should
be the cleanest expression and should dominate.

**What happened:** It barely beats T-bills. Sortino 0.22, +1.2% CAGR,
44% max DD. Negative in the 2013-2017 sub-period. **The simple SMA
rule does not generalize from equities to commodities** — the commodity
universe doesn't have the structural drift that makes the SMA test
meaningful.

### 3.2 V2 — Donchian channel breakout (CTA-classic)

**Definition:** `ENTER long when close > highest close of trailing 100
days; EXIT to flat when close < lowest close of trailing 50 days; hold
between.` Stateful and *asymmetric* (slower exit than entry).

**What it's trying to catch:** The original Turtle Trader signal. Bets
on breakouts to new highs (where MA crossovers lag) and lets winners run
via the slow exit threshold ("give positions room to breathe"). This
signal is what produced the 50-year track record of commodity
trend-following CTAs in the 1970s-1990s.

**Why test it:** It's the strongest test of "do commodities need a
*different* trend signal than equities?" If V2 worked and V1 didn't,
the answer would be yes.

**What happened:** It was the worst of the three. **It actually lost
money** — Sortino −0.19, CAGR −2.6%. The asymmetric slow exit, designed
to let winners run, instead let losers run during the choppy 2010s
commodity bear: enter on a bear-market rally, fail to exit until the
trough, repeat. The classic CTA signal has not worked on this universe
in this regime.

### 3.3 V3 — Vol-adjusted time-series momentum

**Definition:**
```
ratio_t = (12-month return) / (12-month annualized vol)
ON when ratio_t is in the top 50% of its trailing 24-month range
```

**What it's trying to catch:** The academic time-series momentum signal
of Moskowitz, Ooi, and Pedersen (2012). Normalizes momentum by realized
vol (so an instrument with strong but noisy momentum doesn't dominate),
and gates on whether *risk-adjusted* momentum is in the upper half of
its own recent history. This is a **relative / acceleration** signal —
ON only when an instrument's vol-normalized trend is strengthening, not
just present.

**Why test it:** It's the closest thing to the academic consensus on
trend-following, and it tests whether sophisticated normalization beats
the price-only rules. It is also structurally different from V1/V2
(percentile-of-self gate rather than absolute level), so its failure
mode should be different.

**What happened:** It was the only variant that worked. **Sortino 0.71,
+5.3% CAGR, +4.2% after-tax**, 38% max DD. It still fails the sub-period
robustness test (negative in 2013-2017) and only reaches Tier C, but
among the three this is clearly the best signal family. Notable
property: V3 is the only signal that fires meaningfully on grains
(because the "top 50% of own range" gate isn't suppressed by
back-adjustment carry drift the way V1/V2 are).

### 3.4 Shared infrastructure (same for all three)

This is the part of the system that's reusable regardless of signal:

- **Vol-targeted sizing.** Daily 60-day rolling covariance; inverse-vol
  weights scaled so portfolio targets 15% annualized vol; 25% per-
  instrument cap to prevent single-name concentration. Full-covariance
  (not independent-vol) so correlation regimes are respected.
- **T-bill on idle capital.** Days with no ON positions earn 2%/yr (the
  config; can be wired to FRED later). Days where vol-targeting levers
  > 1 pay the same rate as financing.
- **Transaction costs.** Per-sector bid-ask half-spread on weight
  turnover (energy 8 bps round-trip, metals 3-5, grains 5, softs 7) plus
  a per-sector roll cost when a held instrument switches contracts. Net
  cost drag is small (0.4-0.8% per year per variant) and not the reason
  any variant fails.
- **No look-ahead.** Signal computed at close[t-1] drives the return
  earned over [t-1 → t]. Locked early after the equity-strategy
  Convention 1/2 episode and verified by unit test.

---

## 4. What the data showed

### 4.1 Headline (full sample, net of costs)

| Variant | CAGR | Sharpe | Sortino | MaxDD | Vol | AT-CAGR | Tier |
|---|---:|---:|---:|---:|---:|---:|---|
| EW commodity BAH (benchmark) | +2.6% | 0.24 | 0.33 | 70% | 17% | +2.0% | — |
| V1 SMA 50/200 | +1.2% | 0.16 | 0.22 | 44% | 11% | +0.9% | D |
| V2 Donchian 100/50 | −2.6% | −0.14 | −0.19 | 59% | 13% | −2.6% | D |
| V3 Vol-adj momentum | **+5.3%** | **0.49** | **0.71** | **38%** | 12% | **+4.2%** | **C** |

(Tier criteria revised for asset class per the locked methodology:
A ≥1.0 / B ≥0.7 / C ≥0.5 Sortino, plus cross-sub-period robustness, sector
diversification, low correlation with the equity strategy, and a meaningful
lift over the buy-and-hold benchmark.)

### 4.2 Per-sector attribution (cumulative contribution to total P&L)

| Variant | Energy | Precious | Industrial | Grains | Net positive sectors |
|---|---|---|---|---|---:|
| V1 SMA | NG strong, others mixed | Strong (GC+SI) | Negative (HG) | Mostly negative | 2 of 5 |
| V2 Donchian | Mostly negative | Strong (GC+SI) | Negative | Wheat catastrophic | 1 of 5 |
| V3 Momentum | **All four positive** | **Strongest (GC+SI)** | **Positive (HG)** | Wheat hurts; corn small loss | 3 of 5 |

**Precious metals carried every variant.** Gold and silver had clean
trends in 2010-2026 (2011 bubble, 2019-2020 run, 2024-2026 surge) and
were the cleanest case for trend-following. **Wheat was a graveyard
across all three** — bouncy, no sustained direction.

### 4.3 The robustness problem (all variants)

| Variant | 2018-2026 (in-sample) | 2013-2017 (held-out) |
|---|---|---|
| V1 SMA | 0.65 Sortino, +5% CAGR | **−0.51 Sortino, −3% CAGR** |
| V2 Donchian | −0.07, −2% | **−0.88, −7%** |
| V3 Momentum | 1.32, +12% | **−0.43, −4%** |

**Every variant is negative in 2013-2017.** The apparent V3 edge is
specific to the recent window. 2013-2017 was the heart of the commodity
bear (the 2014-16 oil crash from $107 to $26); a long-flat trend system
either sat in T-bills (V1) or got whipsawed buying counter-trend rallies
(V3 lost −29% in that single window).

### 4.4 The diversification finding (the only unambiguous positive)

Correlation of daily net returns with the locked equity strategy (QQQ
50/200 + T-bill OFF):

| Variant | Corr |
|---|---:|
| V1 SMA | +0.09 |
| V2 Donchian | +0.12 |
| V3 Momentum | +0.10 |

**All three sit well under the 0.30 diversifier bar.** Even a mediocre
commodity-trend sleeve is genuinely uncorrelated with the equity
strategy. V3 at 0.10 correlation with 0.71 Sortino is a real diversifier
candidate — just not strong enough as a standalone to deploy.

### 4.5 Cross-variant correlations (high)

| | V1 | V2 | V3 |
|---|---:|---:|---:|
| V1 | 1.00 | 0.79 | 0.69 |
| V2 | 0.79 | 1.00 | 0.71 |
| V3 | 0.69 | 0.71 | 1.00 |

The three trade essentially the same commodity-trend exposure with
different signal noise. There is **no diversification gain from
combining them**, which means we can't ensemble our way out of the
robustness problem.

---

## 5. Verdict (this round)

**Do not deploy commodity trend as a standalone strategy on this
evidence.**

- V1 (simple SMA) does not generalize from equities — Tier D.
- V2 (classic CTA Donchian) **lost money** in the 2010s commodity bear —
  Tier D.
- V3 (vol-adjusted momentum) is a real, modest signal and a genuine
  equity diversifier, but isn't robust across sub-periods — Tier C.

**One survivor worth remembering: V3.** If commodity exposure is ever
revisited — at $25k+ with multi-strategy capacity, or if full-history
data becomes available — V3 is the candidate to resurrect. V1 and V2 can
be set aside.

---

## 6. Why "first run" — what a second pass would do differently

This is genuinely a first pass. Several things could plausibly move the
verdict and were out of scope for this round:

### 6.1 Get the missing data

- **Full history (2000-2009)** would let us see the 2003-2008
  supercycle and the 2008 crash — both textbook trend environments.
  Status: blocked by Norgate trial cap, $270/yr to unlock, not pursued.
- **The 3 ICE instruments** (Brent, Sugar, Coffee) would broaden the
  basket. Sugar and Coffee in particular have classic boom-bust
  dynamics that trend signals historically catch.
- **Note the methodology caveat:** the 2000-2009 commodity market was
  structurally different (pre-financialization, China supercycle), so a
  signal "rescued" by that window might be fragile in 2026+. The
  uncertainty cuts both ways.

### 6.2 Long-short instead of long-flat

The spec locked all three variants as long-flat per the broader research
discipline (no shorting in V1 phase). But **classic CTA trend is
long/short** and that matters more in commodities than equities:
- The 2014-16 oil crash was a textbook short setup ($107 → $26 in
  18 months). A long-short Donchian would have *profited* from it
  instead of sitting out or getting whipsawed.
- Long-short V3 momentum is the actual published Moskowitz/Ooi/Pedersen
  result, with much better performance than the long-only restriction.
- Margin requirements / SIPC limits make shorting commodity futures
  trivial; this is a *signal* restriction, not an account restriction.

A long-short re-run is the single highest-value follow-up if commodity
trend ever gets a second look.

### 6.3 Test additional signal families

The three variants were chosen to triangulate *trend* signals. They all
turned out to be too correlated to provide robustness via ensembling.
Other signal families that aren't trend at all:

- **Carry / roll-yield.** Buy contracts in backwardation, sell those in
  contango. Mechanically uncorrelated with trend. Pedersen et al. show
  this is a separable factor.
- **Curve / basis momentum.** Front-month vs deferred contract spread
  dynamics.
- **Skew / vol-of-vol.** Some commodity instruments have persistent
  return-skew anomalies (e.g., wheat is left-skewed; sell vol).
- **Cross-sector pairs.** Energy vs softs, metals vs grains relative-
  value.

These would address the "all variants negative in 2013-2017" problem in
a way ensembling-trend cannot.

### 6.4 Different vol-targeting / risk parity

Inverse-vol with a 25% cap is the simplest sensible scheme. Alternatives:
- **Risk-parity** (equal risk contribution, requires solving for weights
  via the covariance matrix iteratively)
- **Vol scaling per signal-strength** (size up when signal is "strong",
  not just ON)
- **Lower vol target with leverage** (12% target, lever up to maintain
  CAGR while reducing tail risk)

These are tuning, not fundamental, but they can shift the sub-period
robustness picture.

### 6.5 Different timeframes

We tested daily bars throughout. Commodity futures trend research often
finds different signals work on different horizons:
- Weekly/monthly bars (less noise, slower turnover, lower costs)
- Intraday session momentum (e.g., overnight close-to-open is a
  separable trend signal in some commodities)

Worth a follow-up if someone wants to push commodity trend further.

---

## 7. What this round produced (reusable assets)

Even with a "do not deploy" verdict, the round delivered a complete
commodity-futures research stack:

| Module | Purpose | Status |
|---|---|---|
| `src/data/databento_loader.py` | Continuous-futures loader with roll-aware caching, Sunday-session collapse, instrument_id preservation | ✅ |
| `src/commodity/vol.py` | 60-day rolling covariance, full-covariance vol-targeted weights | ✅ |
| `src/commodity/signals.py` | Three signal variants, per-instrument NaN-safe computation | ✅ |
| `src/commodity/engine.py` | Vol-targeted long-flat portfolio backtest with per-sector roll + spread costs, T-bill on idle | ✅ |
| `src/commodity/metrics.py` | Sortino/Sharpe/CAGR/maxDD + Section 1256 after-tax | ✅ |
| `scripts/build_backadjusted.py` | Panama difference back-adjustment with instrument_id-driven roll detection | ✅ |
| `scripts/run_commodity_backtest.py` | Full M6+M7 comparative runner with tier classification | ✅ |
| `scripts/local_norgate_pull.py` | Parked but verified-working Norgate pull (waiting on subscription) | ⏸ |
| 21 tests | Signal correctness, engine no-lookahead, T-bill-only invariant, etc. | ✅ |

A second-run effort can swap signals (e.g., add carry/long-short
variants) and re-run the engine without touching the data layer. The
expensive infrastructure work is done.

---

## 8. Summary in one paragraph

Commodity trend is genuinely a different problem than equity trend.
Three trend-signal families were tested on 10 CME commodities over
2010-2026; only V3 (vol-adjusted momentum) beats buy-and-hold, reaching
Tier C with a 0.71 Sortino but failing the sub-period robustness test.
V1 (SMA) and V2 (Donchian) fail outright; V2 actually loses money. All
three are excellent equity diversifiers (~0.10 correlation), but their
own internal correlations are high so they can't be ensembled into
robustness. The 2000-2009 backfill and 3 ICE instruments are
deliberately missing; the verdict is on the most-deployment-relevant
window. **Bottom line:** do not deploy standalone; V3 is the one
candidate to resurrect later. The framework is reusable, and a
long-short re-run with carry signals included is the obvious next move
if commodity trend ever gets a second look.
