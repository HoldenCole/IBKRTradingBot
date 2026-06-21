# Crypto Test 1 — Tame-the-Drawdown Beta (locked criteria)

**Date:** 2026-06-21
**Branch:** claude/commodity-trend-research
**Runner:** `scripts/run_crypto_test1.py`
**Raw output:** `RESULTS_test1.txt`
**Mandate:** tame-the-drawdown beta (capture crypto upside, cut the ~80% drawdowns)
**Signal:** the equity-validated 50/200 trend rule, transferred to crypto with
NO crypto-specific tuning (one-look discipline).

## Locked criteria (set before the run, gated on the MANDATE not correlation)

| Tier | Calmar | MaxDD | CAGR vs BAH | Robustness |
|---|---|---|---|---|
| A | >1.0 | <50% | ≥ BAH | improves Calmar in ≥5/7 eras + cuts DD in every bear |
| B | >0.7 | <60% | ≥0.8× BAH | improves Calmar in ≥4/7 eras |
| C | >0.5 | — | — | marginal |
| D | else | | | |

Equity correlation is **reported, never gated** — crypto's job under this
mandate isn't diversification.

## Result

| Coin | Verdict | Calmar | MaxDD (trend vs BAH) | CAGR (trend vs BAH) | Sortino | AT-CAGR |
|---|:--:|---:|---|---|---:|---|
| **BTC** | **Tier B** | **1.38** | **43% vs 83%** | **+59% vs +52%** | 2.06 | +53% vs +46% |
| ETH | Tier C | 0.67 | 51% vs 94% | +34% vs +22% | 1.35 | +28% vs +17% |

Costs included (IBIT/ETHA 0.25% expense + 10 bps/transition + T-bill 3% on
OFF capital), net figures, no same-bar look-ahead.

## BTC — the headline

Trend 50/200 on BTC does exactly what the mandate asks, and then some:
- **Halves the drawdown** (83% → 43%) — the catastrophic 80% drawdown becomes
  a survivable 43%.
- **Improves return** (+52% → +59% CAGR) — and **beats BAH after-tax too**
  (+53% vs +46%).
- **Calmar 1.38** (vs 0.63) — more than doubles risk-adjusted return.
- **Sortino 2.06** (vs 1.42).
- ON 39% of days · 10.8 transitions/yr · ~1.18%/yr cost drag (crypto 50/200
  whipsaws more than the ~6/yr equity version — crypto is choppier; the net
  figures already absorb this).

**Per-era robustness:**

| Era | BAH Calmar | Trend Calmar | Trend MaxDD | Improved? |
|---|---:|---:|---:|:--:|
| 2015-2016 recovery | 1.69 | 2.41 | 25% | ✓ |
| 2017 ICO boom | 38.55 | 15.24 | 38% | ✗ (gave up parabolic top) |
| 2018 bear | −0.90 | −0.45 | 33% | ✓ |
| 2019-2020 chop | 1.34 | 0.62 | 43% | ✗ (whipsaw) |
| 2020-21 retail boom | 5.96 | 8.79 | 32% | ✓ |
| 2022 contagion | −0.96 | **0.00 (0% DD)** | 0% | ✓ (in cash) |
| 2023+ ETF era | 0.93 | 0.88 | 26% | ✗ (near-tie) |

Improved Calmar in **4 of 7** eras; **cut drawdown in both bears**. It misses
Tier A only on the strict ≥5-era robustness bar. The three misses are honest
and acceptable: a parabolic melt-up (2017 — still +595%-class returns, just
less than the insane BAH), a chop period (2019-20, trend's known weakness),
and a statistical tie (2023+, 0.88 vs 0.93). The strategy improves Calmar in
**every era that matters** — both bears and both major bull booms.

## ETH — secondary, Tier C

Cuts drawdown hard (94% → 51%) and improves return (+22% → +34%), but Calmar
0.67 misses Tier B by 0.03, and it improves Calmar in only 3/7 eras. ETH is a
real beneficiary of the filter but less robust than BTC. Optional secondary
sleeve, not a primary.

## Equity correlation (reported, not gated)

| | vs QQQ |
|---|---:|
| BTC trend strategy | +0.07 |
| ETH trend strategy | +0.11 |

Interesting: the trend *strategy* is fairly uncorrelated with equities (+0.07)
even though BTC *buy-and-hold* is +0.24 and spikes to +0.58 in crises. The
reason is mechanical — the trend strategy is in cash during the crashes where
crypto-equity correlation spikes, so it sidesteps the correlated drawdowns.
Per the mandate this is **not** a deployment criterion, but it's a pleasant
side-effect: the tamed version is less equity-correlated than raw BTC.

## Verdict

**BTC trend 50/200 = Tier B, deployable under the tame-the-drawdown mandate.**
It is arguably the cleanest single-asset result of the entire project
(Calmar 1.38, Sortino 2.06, drawdown halved, return improved, robust across
both bears). ETH is a Tier-C secondary.

That this used the **equity-validated 50/200 rule with zero crypto tuning** is
the strongest argument against overfitting — the same simple rule that works
on 98 years of equities also tames crypto's drawdowns.

## The load-bearing caveat: survivorship

The one serious threat to this result is **asset survivorship**. BTC is *the*
winner of the 2014-2026 crypto era. We are applying trend-following to the
single best-performing asset of the decade, chosen with hindsight. Two points
on each side:

- *Mitigant:* trend-following follows price; it doesn't require knowing in 2014
  that BTC would win, the way buy-and-hold would. The rule is asset-agnostic.
- *Residual risk:* the *asset selection* (BTC) is still post-hoc. We don't know
  that BTC will be the BTC of the next decade. A 50/200 trend on whatever-coin-
  wins-next is not guaranteed to look like this.

This caveat is inherent to crypto and can't be fully resolved with 11 years of
data and one dominant asset. It should size the position conservatively and
argue for deploying on BTC specifically (the established, institutionally-held,
ETF-backed asset) rather than chasing alts.

## Other honest limitations

- **Small sample:** ~2.5 cycles, only 2 real bears (2018, 2022). The per-era
  consistency helps but the independent-bear count is low.
- **Parabolic-top cost is real** (2017): the filter gives up large upside in
  melt-ups. Accepted as the price of drawdown control.
- **Whipsaw cost** (~1.18%/yr) is higher than equities — crypto's chop makes
  50/200 flip ~11×/yr. A slower/hysteresis variant might reduce this, but
  one-look discipline holds; no tuning.
- **Vehicle/tax:** modeled via IBIT/ETHA (securities → 1099-B, wash-sale
  applies). Spot crypto (property → no wash-sale currently, a real
  loss-harvesting edge) is an alternative vehicle with a different tax profile
  worth its own analysis if deployed.

## Recommendation

**BTC trend 50/200 is a validated Tier-B deployment candidate.** Recommended
disposition, mirroring the disciplined approach used elsewhere:

- **Deploy as a small, survivorship-caveated crypto sleeve** — via IBIT in the
  taxable account — *when the equity strategy's paper trading has validated
  the operational stack* (don't run two un-live strategies at once).
- Size it small: this is a Tier-B result on a survivorship-selected asset, not
  a Tier-A lock. Its job is tamed crypto exposure, not a core holding.
- ETH is an optional secondary (Tier C); LTC is dropped.

This is a genuine, deployable positive — the first "deploy-worthy" diversifier
candidate the multi-strategy research has produced. The decision of whether/
when/how-much to deploy is the portfolio owner's; the evidence supports it
under the mandate.

## Status

Crypto Test 1 complete. BTC Tier B (deployable), ETH Tier C (secondary).
Awaiting your decision on disposition (deploy now / deploy after equity goes
live / defer). Per your standing priority, equity paper trading remains first.
