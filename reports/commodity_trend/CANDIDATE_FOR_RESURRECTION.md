# DEFERRED DEPLOYMENT CANDIDATE — Long-Short V3 Commodity Trend

**Status:** Not deployed. Filed for re-evaluation when multi-strategy
becomes viable (**$25k+ account**).
**Filed:** 2026-06-21
**Branch:** claude/commodity-trend-research

> Future-you: this is the one commodity strategy worth resurrecting. Carry
> is dead (see `07_test2_carry_and_conclusion.md`). V1 SMA and V2 Donchian
> failed. **Long-short V3 trend is the candidate.** Everything you need to
> re-run it is built and tested.

## Why this is deferred, not deployed

It missed the Tier-B bar by **0.03 Sortino (0.67 vs 0.70)** — but on the
metric the mandate explicitly de-emphasized. On the metric the mandate
actually cared about (crisis diversification), it is a clear success. Rather
than rationalize an override or rigidly enforce a rule with a baked-in
methodological inconsistency, the decision was deferred to when it matters.
Deploying now isn't required; losing the option would be a mistake. This
doc preserves the option at zero cost.

## THE LOAD-BEARING FINDING — crisis profile

This is the evidence that makes the candidate worth keeping. Long-short V3
during equity-stress windows (commodity strategy return vs the locked equity
strategy QQQ 50/200 + T-bill OFF):

| Equity-stress regime | Commodity return | Equity return | Correlation |
|---|---:|---:|---:|
| Full sample | — | — | **−0.05** |
| 2014-16 oil crash | **+33.5%** | −8.4% | −0.06 |
| 2018-Q4 correction | **+11.5%** | −3.0% | +0.12 |
| 2020 March COVID | **+22.4%** | −8.2% | −0.11 |
| 2022 inflation bear | **+6.5%** | −3.4% | +0.01 |
| 2025 Liberation Day | −5.2% | −1.5% | −0.03 |

**Positive in 4 of 5 equity-stress windows. Negative or near-zero
correlation in every crisis.** This is the textbook crisis-diversifier
profile — exactly what a commodity sleeve should provide that the equity
strategy can't.

## Full-sample metrics (2010-2026, net of costs)

| Metric | Value |
|---|---:|
| Sortino | 0.67 |
| CAGR | +5.7% |
| After-tax CAGR (Sec 1256) | +4.6% |
| Max drawdown | 27% |
| Vol | 14% |
| 2018-2026 sub-period Sortino | +0.71 |
| 2013-2017 sub-period Sortino | +0.69 |
| Sectors positive | 3 of 4 (energy, precious, industrial; grains drag) |

Both sub-periods positive — the long-short structure (shorting downtrends)
fixed the first-pass long-flat failure in 2013-2017.

## The exact strategy definition

```
Signal: V3 vol-adjusted momentum, long-short
  ratio_t = (12-month return) / (12-month annualized vol)    per instrument
  LONG  (+1) when ratio_t in top 1/3 of trailing 24-month [min,max] range
  SHORT (−1) when ratio_t in bottom 1/3 of that range
  FLAT  ( 0) in the middle 1/3

Universe: 10 CME commodities — CL, NG, HO, RB, GC, SI, HG, ZC, ZS, ZW
Sizing:   full-covariance vol-targeting, 15% target, 25% per-instrument cap
Accounting: futures-collateral (capital earns T-bill; long/short futures overlay)
Costs:    per-sector roll + bid-ask (energy 8bps, metals 3-5, grains 5, softs 7)
Execution: signal at close[t-1] sizes the book earning return[t] (no lookahead)
```

## How to re-run it (one command)

```bash
python scripts/run_commodity_test1_ls.py
```

Produces the headline metrics, sub-period robustness, per-sector
attribution, and the per-regime correlation table above.

**Code locations:**
- Signal: `src/commodity/signals.py` → `vol_adj_momentum_ls()`
- Sizing: `src/commodity/vol.py` → `vol_target_weights_signed()`
- Engine: `src/commodity/engine.py` → `run_backtest_ls()`
- Data: `src/data/databento_loader.py` (Databento; data gitignored under
  `data/commodities/`)
- Tests: `tests/commodity/` (28 passing)

## What to do at the $25k+ re-evaluation

1. **Re-run against then-current criteria** — and fix the methodological
   flaw: gate on crisis-period correlation + crisis-period return, NOT
   full-sample Sortino (see DECISIONS.md lesson).
2. **Use then-available information:**
   - Live equity-strategy results (is the 0.10 / −0.05 correlation holding
     out of sample?)
   - Any new equity-stress events since 2026 (each is a fresh crisis test)
   - Crypto strategy results, if that workstream produced a deployable
     diversifier (compare which diversifies the equity book better)
3. **Consider the deferred data** — if Norgate ($270) was ever acquired,
   run the 2000-2009 robustness test on long-short V3 (the supercycle + 2008
   crash is the missing trend environment).
4. **If it's still the best available commodity candidate, deploy it** as a
   small crisis-hedge sleeve within the multi-strategy book — sized for the
   diversification benefit, not as a return driver.

## What NOT to revisit

- **Carry** — closed permanently (Tier D, loses money). Only reopen on a
  published structural improvement to term-structure modeling.
- **V1 SMA / V2 Donchian** — failed; set aside.
- **Parameter tuning of V3** — one-look discipline held; don't tweak to
  chase the 0.03 Sortino. If re-evaluating, change the *criteria* (per the
  methodological lesson), not the signal parameters.
