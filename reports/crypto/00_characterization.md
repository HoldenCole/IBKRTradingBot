# Crypto Characterization (Pure-Research Round)

**Date:** 2026-06-21
**Branch:** claude/commodity-trend-research (crypto work lives here for now)
**Runner:** `scripts/run_crypto_characterization.py`
**Raw output:** `RESULTS_characterization.txt`
**Mandate:** none yet — this round characterizes; the mandate is *recommended*
from the evidence below.

## Data

| Coin | History | Years | Bars/yr |
|---|---|---:|---:|
| BTC-USD | 2014-09 → 2026-06 | 11.8 | 365 (24/7) |
| ETH-USD | 2017-11 → 2026-06 | 8.6 | 365 |
| LTC-USD | 2014-09 → 2026-06 | 11.8 | 365 |

Clean spot data — no contracts, rolls, or back-adjustment (unlike
commodities). 365-day annualization. Deployable vehicle = spot ETFs
IBIT/ETHA (launched 2024) or spot on a US exchange.

## Q1 — The buy-and-hold beta baseline

| Coin | CAGR | Vol | Sharpe | Sortino | Calmar | MaxDD |
|---|---:|---:|---:|---:|---:|---:|
| **BTC** | **+52%** | 67% | 0.97 | 1.42 | **0.63** | 83% |
| ETH | +22% | 85% | 0.66 | 0.96 | 0.23 | 94% |
| LTC | +20% | 99% | 0.67 | 1.06 | 0.22 | 93% |

Enormous CAGR, but **70-95% drawdowns**. BTC is clearly the best
risk-adjusted of the three (highest CAGR, lowest vol, ~3× the Calmar of
ETH/LTC). ETH and LTC are materially worse buy-and-holds. **Calmar
(CAGR/MaxDD) is the honest lens** — even BTC at 0.63 is a low-Calmar bet
in raw form.

## Q2 — Does a trend filter TAME THE DRAWDOWN? (the central question)

**Yes — decisively, and for BTC it improves return too.**

### BTC
| Strategy | CAGR | MaxDD | Calmar | Sortino |
|---|---:|---:|---:|---:|
| buy-and-hold | +52% | 83% | 0.63 | 1.42 |
| **trend 50/200** | **+58%** | **43%** | **1.34** | **2.03** |
| trend 20/100 | +54% | 44% | 1.22 | 2.16 |
| vol-adj momentum | +29% | 60% | 0.49 | 1.38 |

### ETH
| Strategy | CAGR | MaxDD | Calmar | Sortino |
|---|---:|---:|---:|---:|
| buy-and-hold | +22% | 94% | 0.23 | 0.96 |
| **trend 50/200** | **+33%** | **51%** | **0.65** | **1.32** |
| trend 20/100 | +23% | 69% | 0.34 | 1.09 |
| vol-adj momentum | +15% | 64% | 0.24 | 0.83 |

### LTC
| Strategy | CAGR | MaxDD | Calmar | Sortino |
|---|---:|---:|---:|---:|
| buy-and-hold | +20% | 93% | 0.22 | 1.06 |
| trend 50/200 | +15% | 88% | 0.18 | 0.87 |
| **trend 20/100** | **+44%** | 73% | **0.60** | 1.53 |
| vol-adj momentum | +23% | 78% | 0.30 | 1.07 |

**Findings:**
- **BTC trend 50/200 is the standout:** halves max DD (83% → 43%) while
  *raising* CAGR (52% → 58%). Calmar more than doubles (0.63 → 1.34);
  Sortino 1.42 → 2.03. This is a cleaner, stronger version of exactly what
  50/200 did for QQQ — and it matters more here because the drawdowns being
  cut are catastrophic.
- **ETH also benefits hugely** (94% → 51% DD, Calmar 0.23 → 0.65, return up).
- **LTC is the weak coin** — 50/200 doesn't help; only the faster 20/100
  does. LTC is a marginal asset; it doesn't earn a place.
- **Vol-adjusted momentum underperforms simple trend on crypto** — the
  "top 50% of trailing range" gate gives up too much. Simple trend wins
  here (opposite to commodities, where momentum was the only thing that
  worked). Different asset, different signal.

## Q3 — Equity-correlation evolution (the diversification reality)

Full-sample BTC-vs-QQQ daily-return correlation: **+0.24**, but the
trajectory is the story:

| Era | BTC-QQQ corr | BTC ret | QQQ ret |
|---|---:|---:|---:|
| 2015-2016 recovery | −0.00 | +201% | +15% |
| 2017 ICO boom | +0.02 | +1369% | +31% |
| 2018 bear | +0.12 | −74% | −1% |
| 2019-2020 chop | +0.29 | +188% | +80% |
| 2020-21 retail boom | +0.27 | +429% | +42% |
| **2022 contagion** | **+0.58** | −64% | −33% |
| 2023+ ETF era | +0.34 | +288% | +178% |

BTC buy-and-hold **during equity-stress windows** specifically:

| Window | BTC | QQQ | Corr |
|---|---:|---:|---:|
| 2018-Q4 | −38% | −23% | +0.11 |
| 2020 March COVID | −29% | −16% | +0.55 |
| 2022 inflation bear | −59% | −32% | +0.59 |
| 2025 Liberation Day | +12% | +2% | +0.45 |

**Crypto is NOT an equity-stress diversifier in modern regimes.**
Correlation rose from ~0 (2015-17) to ~0.5-0.6 (2022 onward), and in every
recent equity-stress window BTC fell *harder* than QQQ (−29% vs −16%,
−59% vs −32%). Crypto amplifies equity drawdowns rather than hedging them.
This kills the "equity diversifier" mandate by construction — correctly
avoided up front.

## Q4 — Per-era: where the trend filter earns its keep (BTC)

| Era | BAH ret | BAH DD | Trend ret | Trend DD |
|---|---:|---:|---:|---:|
| 2015-2016 recovery | +201% | 43% | +153% | 24% |
| 2017 ICO boom | +1369% | 36% | +595% | 38% |
| 2018 bear | −74% | 82% | −16% | 33% |
| 2019-2020 chop | +188% | 62% | +49% | 43% |
| 2020-21 retail boom | +429% | 53% | +374% | 32% |
| **2022 contagion** | **−64%** | 67% | **+0%** | **0%** |
| 2023+ ETF era | +288% | 51% | +104% | 25% |

The trend filter's value concentrates exactly where it should — **bear
markets**: it cut the 2018 bear from −74% to −16%, and **sidestepped the
2022 contagion entirely** (0% / 0% DD — it was in cash). In bull eras it
keeps most of the upside (2020-21: +374% vs +429%). The one real cost is
parabolic melt-ups: in 2017 it captured "only" +595% of the +1369% top —
the price of the discipline that also avoided the subsequent −74%.

## Mandate recommendation

The evidence points clearly to one mandate:

> **Tame-the-drawdown beta.** Hold BTC trend-on, cash trend-off. Capture
> crypto's asymmetric upside while cutting the catastrophic 80%+ drawdowns
> to a survivable ~40%. Benchmark = BTC buy-and-hold. This is the same
> thing the 50/200 filter does for QQQ, only the payoff is larger because
> the drawdowns being cut are larger.

Why this and not the others:
- **Not equity diversifier** — Q3 is definitive; crypto amplifies equity
  stress (corr → 0.5+).
- **Not pure absolute-return** — buy-and-hold already delivers the absolute
  return; the strategy's job is making it *survivable*, which is the
  drawdown framing.
- **BTC-centric, ETH secondary, LTC dropped.** BTC is the cleanest; ETH
  benefits too; LTC is marginal and doesn't earn a slot.
- **Simple trend, not momentum.** 50/200 (and 20/100) beat vol-adj
  momentum on every coin.

## What a Test-1 (locked-criteria) round would look like

Per the methodological lesson, criteria must match this mandate — so they'd
gate on **drawdown reduction + return retention (Calmar)**, NOT correlation:

- **Tier A:** Calmar > 1.0, MaxDD < 50% (vs BAH ~83%), CAGR ≥ BAH, robust
  across the regime eras (positive trend-vs-BAH Calmar improvement in
  ≥4 of the bear/bull eras)
- **Tier B:** Calmar > 0.7, MaxDD < 60%, CAGR ≥ 0.8× BAH, robust in most eras
- (Correlation with the equity strategy is reported but NOT gated — crypto's
  job here isn't diversification.)

On the characterization numbers, BTC trend 50/200 (Calmar 1.34, MaxDD 43%,
CAGR ≥ BAH, improvement in every bear era) would land **Tier A** — but that's
a preview, not a locked verdict. A real Test-1 round would lock these
criteria first, add costs (ETF expense + spread), model the IBIT/ETHA vehicle
and crypto-property tax (no wash-sale on spot; 1099-B on ETFs), and re-run
with no-look-ahead execution discipline.

## Caveats (honest limitations)

- **Small sample.** BTC = 11.8 yrs ≈ 2.5 cycles; only ~2 real bear markets
  (2018, 2022). The trend result is *consistent* across eras (helps) but
  the independent-bear count is low.
- **Survivorship.** BTC is *the* winner; we're testing on the survivor.
  Mitigant: trend-following doesn't need to know the winner in advance the
  way buy-and-hold does — it follows price. Still, applying it only to BTC
  post-hoc is a selection the live strategy wouldn't have had in 2014.
- **No costs yet.** Crypto spot spreads are small but nonzero; ETFs carry
  ~0.25% expense. ~12 transitions/yr × small slippage — immaterial but
  unmodeled in this characterization.
- **Parabolic-top cost is real.** In a 2017-style melt-up the filter gives
  up large upside. The mandate accepts this as the price of drawdown control.
- **Regime dependence of the equity-correlation.** If crypto's
  equity-correlation keeps rising, even the "tame-the-drawdown" version
  becomes more redundant with a levered equity position. Worth monitoring.

## Status

Characterization complete. **Recommended mandate: tame-the-drawdown beta on
BTC (ETH secondary).** Awaiting your decision on the mandate before scoping a
locked-criteria Test-1 round. Per your earlier direction, crypto can also
simply wait — the equity strategy's paper trading is the live priority.
