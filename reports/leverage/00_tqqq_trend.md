# TQQQ Trend Test — does 50/200 survive 3x leveraged-ETF decay?

**Date:** 2026-06-22
**Runner:** `scripts/run_tqqq_trend.py`
**Raw output:** `RESULTS_tqqq.txt`
**Verdict:** **Tier D**. Leverage amplifies whipsaw approximately as much as
it amplifies returns; Calmar doesn't improve. Don't deploy.

## The locked criteria (set before the run)

| Tier | Calmar | MaxDD | CAGR vs QQQ trend | Bears cut |
|---|---|---|---|---|
| A | >1.0 | <50% | ≥1.5× | both 2018-Q4 & 2022 |
| B | >0.7 | <60% | ≥1.2× | — |
| C | >0.5 | — | — | — |
| D | else | | | |

## Result

| Strategy | CAGR | MaxDD | Calmar | Sortino | Vol |
|---|---:|---:|---:|---:|---:|
| QQQ buy-and-hold | +29% | 36% | 0.80 | 1.62 | 25% |
| TQQQ buy-and-hold | +70% | **82%** | 0.85 | 1.55 | 74% |
| QQQ 50/200 (deployed baseline) | +12% | 22% | 0.55 | 1.24 | 14% |
| **TQQQ 50/200 (the test)** | **+21%** | **55%** | **0.38** | 0.95 | 38% |

| Criterion | Required | Actual | Pass? |
|---|---|---:|:--:|
| Calmar > 0.5 (Tier C floor) | >0.5 | **0.38** | ✗ |
| Calmar > 0.7 (Tier B) | >0.7 | 0.38 | ✗ |
| MaxDD < 60% (Tier B) | <60% | 55% | ✓ |
| CAGR ≥ 1.5× QQQ trend (Tier A) | ≥1.5× | 1.70× | ✓ |
| Bears cut (Tier A) | both | both | ✓ |

**TIER D** — fails Tier C's standalone Calmar floor. The CAGR multiple and
bears-cut criteria pass, but the risk-adjusted result doesn't improve over
the baseline.

## Why — the per-era breakdown shows the mechanism

| Era | TQQQ BAH (CAGR/DD) | TQQQ trend | QQQ trend |
|---|---|---|---|
| 2011-2015 post-GFC | +44% / 44% | **+1% / 50%** | +3% / 18% |
| **2015-2016 chop** | +14% / 45% | **−28% / 49%** | −10% / 18% |
| 2017 melt-up | +119% / 15% | **+73% / 21%** | +22% / 7% |
| 2018-Q4 correction | −97% / 58% | **−20% / 6%** | −11% / 3% |
| 2020 COVID + recovery | +69% / 70% | +17% / 45% | +14% / 19% |
| 2020-21 retail boom | +202% / 35% | +35% / 45% | +17% / 19% |
| 2022 inflation bear | −79% / 81% | **−9% / 13%** | −2% / 4% |
| 2023-2026 ETF/AI | +93% / 58% | +26% / 32% | +21% / 12% |

Three honest readings:

1. **Whipsaws are amplified ~3x.** 2015-2016 chop: QQQ trend lost −10%,
   TQQQ trend lost **−28%**. The 50/200 generates plenty of false signals on
   the underlying; on a 3x ETF those become catastrophic.

2. **Even in clean bull markets, leverage captures only ~2x not 3x.**
   2020-21 retail boom: QQQ trend +17%, TQQQ trend +35% (2.06x). The trend
   strategy's entries/exits (~20/yr) eat enough of the leverage that you
   never get the full 3x exposure even when conditions are favorable.

3. **Bears WERE cut** (2018-Q4: −97% BAH → −20% trend; 2022: −79% → −9%) —
   the trend filter did its job on the downside. But the savings were
   already inside the leverage; they don't compound into a better Calmar.

## The structural finding

TQQQ trend is a roughly proportional scale-up of QQQ trend: ~1.7-2× the
CAGR, ~2.5× the drawdown, **0.7× the Calmar**. The 3x leverage doesn't
free-ride on the trend filter's exit logic — the daily-reset compounding
introduces enough additional whipsaw friction that you don't get a better
risk-adjusted result, just a bigger-numbers version of the same trade.

This is the answer to the queue's central question: **does the trend
filter's exit logic save TQQQ from its decay penalty?** Partially — it does
keep the drawdown to 55% (vs BAH's 82%) — but not enough to produce a
Calmar improvement over the unlevered version. The "leveraged-trend gives
you the upside without the drawdown" thesis fails empirically.

## Costs were honest, not the cause

| Cost component | Value |
|---|---|
| TQQQ expense ratio | 0.84%/yr (held in ON periods) |
| Transition slippage | 20 bps/trade |
| ON fraction | 54% of days |
| Transitions/yr | 19.9 |
| **Total cost drag** | **4.43%/yr** |

That's a real drag but not what kills the verdict. Even at zero cost the
Calmar would still be ~0.5, still Tier C. The structural decay/whipsaw
cost is the mechanism.

## Implication for the deployment plan

**No change to the deployed portfolio.** QQQ 50/200 stays the equity sleeve.
TQQQ trend isn't a Basket-1 leveraged alternative — it's an inferior version
of the same trade.

This DOES leave the "how to get leveraged equity exposure for the
return-stage at $25k+" question open. The remaining candidate is **1 MES
futures** — see `01_mes_vehicle_analysis.md` and `02_mes_vs_qqq_index_test.md`.
Futures-based leverage has different mechanics (no daily reset → no decay)
and Section 1256 tax treatment, which the TQQQ ETF mechanism can't access.

## What we learned (worth keeping)

- **Leveraged ETF + trend filter is not a free lunch.** The popular
  "TQQQ-with-trend" idea, often presented as a Sharpe enhancement, doesn't
  hold up under honest Convention-2 backtest with locked criteria.
- **The decay penalty IS partially mitigated by the trend exit** (TQQQ BAH
  drawdown 82% → TQQQ trend 55%), but not enough.
- **Whipsaws are the dominant friction**, not expense ratio. A
  lower-whipsaw signal (slower MAs?) might shift this — but per one-look
  discipline, no tuning. The locked 50/200 result is the answer.

## Status

TQQQ trend closed. No deployment. Continue to MES research (Items 2a + 2b)
for futures-based leveraged equity at higher account sizes.
