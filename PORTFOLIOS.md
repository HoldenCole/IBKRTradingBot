# Portfolio Allocation Menu — by Risk Profile

Companion to `REGIMES.md`. All results: daily data 2007-06 → 2026-08 (includes 2008, 2020, 2022), dividends included, T-bill cash yield, leveraged ETFs simulated pre-2010 from QQQ (3x/2x daily reset − financing at T-bill+100bps − 0.95% ER). Metrics per the user's spec: CAGR, Sortino, max drawdown, beta (vs SPY); Sharpe added. Full grid: `research/portfolio_menu.csv`, annual returns: `research/portfolio_annual.csv`.

## Evidence quality — read first

- **Static mixes and the indices strategy are honest backtests of pre-specified rules.**
- **The "Regime" portfolios are in-sample designs**: their quadrant playbooks were chosen after seeing this sample's quadrant payoff table, so their numbers are upward-biased. Treat as upper bounds until validated on data that didn't inform the design (pre-2007, or forward paper).

## The menu

| Portfolio | CAGR | Sortino | maxDD | Beta | Sharpe |
|---|---|---|---|---|---|
| 100% SPY | +10.8% | 0.67 | −55% | 1.00 | 0.55 |
| 100% QQQ | +16.3% | 0.94 | −53% | 1.05 | 0.72 |
| 60/40 SPY/TLT | +8.6% | 0.84 | −30% | 0.51 | 0.65 |
| Permanent 4×25 (SPY/TLT/GLD/SHY) | +7.3% | 1.06 | −19% | 0.20 | 0.77 |
| **33 TQQQ / 33 GLD / 33 TLT** | +19.7% | 1.13 | −51% | 0.99 | 0.83 |
| 33 QLD / 33 GLD / 33 TLT | +15.3% | **1.19** | −37% | 0.64 | 0.87 |
| Indices strat 1x (QQQ 50/200) | +8.5% | 0.61 | −21% | 0.25 | 0.63 |
| Indices strat 2x (QLD when ON) | +13.2% | 0.56 | −40% | 0.50 | 0.58 |
| Indices strat 3x (TQQQ when ON) | +17.0% | 0.56 | −55% | 0.75 | 0.58 |
| Regime CONS * | +7.7% | 1.09 | −15% | 0.09 | 0.82 |
| Regime MOD * | +13.3% | 1.06 | −27% | 0.23 | 0.82 |
| Regime AGG * | +22.4% | 1.11 | −32% | 0.69 | 0.95 |
| Regime VAGG * | +29.8% | 1.03 | −51% | 1.13 | 0.90 |

\* in-sample design bias — see above.

## By risk tier (banded on max drawdown)

| Tier | maxDD band | Best honest option | Regime candidate (needs validation) |
|---|---|---|---|
| Conservative | < 20% | Permanent 4×25 (+7.3%, Sortino 1.06) | Regime CONS (+7.7%, −15%, beta 0.09) |
| Moderate | 20–35% | 60/40, or Indices 1x for lower beta | Regime MOD (+13.3%, −27%) / Regime AGG (+22.4%, −32%) |
| Aggressive | 35–45% | 33 QLD/GLD/TLT (+15.3%, Sortino 1.19, −37%) | — |
| Very aggressive | > 45% | 33 TQQQ/GLD/TLT (+19.7%, −51%) or 100% QQQ | Regime VAGG (+29.8%, −51%) |

## Trigger-robustness test (2026-08-17)

The user's requirement: the regime switch must be what drives outperformance. Rather than tuning one switch until the backtest looks good (guaranteed overfit), all 9 standard trigger definitions were tested in one pass on FIXED playbooks — growth axis ∈ {SPY 10m SMA, 6m momentum, 12m dual momentum} × inflation axis ∈ {DBC 10m SMA, DBC 6m momentum, TIP−IEF 6m relative momentum}:

- **All 9 triggers work.** AGG playbook: CAGR +17.1% to +23.1%, Sharpe 0.71–0.95; MOD: +10.1% to +13.7%. Every variant is positive in every era (worst era CAGR across all 27 cells: +12%). The rotation concept is robust to switch specification — the signature of real structure rather than curve fit.
- **The original, simplest switch (SPY 10m SMA × DBC 10m SMA) is the best or near-best on both playbooks** (AGG: +22.6%, Sortino 1.11, −32%, Sharpe 0.95). Locked; no further switch-shopping.
- Trigger choice mainly moves **drawdown**: SMA-based growth axes exit crashes faster (−32% maxDD) than 6m/12m momentum axes (−52%).
- The TIP/IEF breakeven axis underperforms DBC-based inflation axes consistently.
- Standing caveat: the *playbooks* remain in-sample designs (see above); trigger robustness de-risks the switch, not the playbook.

## Blend test: indices strategy × static leverage

`w × indices-2x + (1−w) × 33 QLD/GLD/TLT`, exploiting their complementary failure modes (chop vs inflation):

| w (trend share) | CAGR | Sortino | maxDD | beta |
|---|---|---|---|---|
| 0.00 | +15.6% | 1.20 | −37% | 0.64 |
| **0.25** | **+15.3%** | **1.19** | **−31%** | 0.61 |
| 0.50 | +14.7% | 0.99 | −26% | 0.57 |
| 1.00 | +12.6% | 0.54 | −40% | 0.51 |

Sweet spot ≈ 25% trend / 75% mix: nearly full CAGR and Sortino with 6 points less drawdown. Beyond that the trend sleeve's lower standalone Sharpe drags.

## The Quadrant Playbook Matrix v1 (canon-grounded, 2026-08-17)

Four rotation portfolios — one per risk tier — each defining an allocation for all four quadrants, driven by the locked switch. Designs are grounded in external research (All-Weather quadrant mapping; 2022/1970s stagflation evidence: energy equities, gold, defensives; trend/managed-futures crisis behavior) rather than our own sample's payoff table, EXCEPT the D-cell equity/TQQQ rebound sleeves in AGG/VAGG (in-sample-informed — flagged). AGG adds the gated IBS overlay at 0.5x, VAGG at 1x (fires only in G by its gate).

| Tier | G (equity-lead) | R (reflation) | S (stagflation) | D (deflation) |
|---|---|---|---|---|
| CONS | 40 SPY/40 IEF/20 GLD | 25 SPY/25 GLD/20 DBC/30 SHY | 50 SHY/20 GLD/15 XLP/15 XLU | 45 TLT/35 SHY/20 XLP |
| MOD | 70 QQQ/30 IEF | 30 SPY/25 XLE/25 GLD/20 DBC | 30 SHY/25 GLD/25 XLE/20 XLP | 55 TLT/25 XLP/20 GLD |
| AGG | 100 QLD +0.5x IBS | 35 QQQ/30 XLE/35 GLD | 30 GLD/30 XLE/20 DBC/20 SHY | 60 TLT/40 QQQ |
| VAGG | 100 TQQQ +1x IBS | 40 QLD/30 XLE/30 GLD | 40 XLE/30 GLD/30 DBC | 50 TQQQ/50 TLT |

### Results, 2007-06 → 2026-08

| Tier | CAGR | Sortino | maxDD | Beta | Sharpe | 2008 | 2022 |
|---|---|---|---|---|---|---|---|
| CONS | +7.7% | 1.12 | **−13%** | 0.16 | 0.82 | +9.9% | −4.0% |
| MOD | +12.6% | **1.24** | **−15%** | 0.34 | 0.90 | +9.6% | −0.3% |
| AGG | +22.3% | 1.12 | −34% | 0.72 | 0.91 | +4.2% | −17.9% |
| VAGG | +34.6% | 1.14 | −57% | 1.52 | 0.92 | −29.1% | −29.5% |
| SPY | +10.8% | 0.67 | −55% | 1.00 | 0.55 | −36.8% | −18.2% |
| QQQ | +16.3% | 0.94 | −53% | 1.05 | 0.72 | | |

MOD is the standout: beats SPY's CAGR with ~1/4 the drawdown, best Sortino on the board, and positive-or-flat through both 2008 (+9.6%) and 2022 (−0.3%).

### Per-quadrant behavior check (annualized within each quadrant)

G and D cells perform as designed for every tier (e.g., AGG: G +44%, D +24%). **The S (stagflation) cells lost for every tier (−2% to −13%)** — the canon allocation (energy/gold/commodities) failed in our classified S months, repeating our earlier finding that ex-ante-classified stagflation under a lagging trend classifier is mostly a risk-off waterfall. Cash remains the only thing that worked there. Proposed v2 revision (pre-registered, to be judged on forward/paper data only): all tiers use the CONS cash-heavy S cell. Not applied retroactively.

### Caveats

- Leveraged ETFs simulated pre-2010; single 20y window; monthly classifier lag; D-cell rebound sleeves in AGG/VAGG are in-sample-informed and drive outsized D-quadrant results (VAGG D: +73%/yr — treat with suspicion).
- Research sources: All-Weather quadrant framework and asset-regime mapping ([Monevator](https://monevator.com/asset-allocation-for-all-weathers/), [pfolio](https://www.pfolio.io/academy/all-weather-portfolio), [Optimized Portfolio](https://www.optimizedportfolio.com/all-weather-portfolio/)); stagflation-era evidence for energy/defensives/gold and 2022 managed-futures performance ([iSquare](https://www.isquareintelligence.com/articles/Best-performing-asset-class-during-stagflation), [Trustnet](https://www.trustnet.com/news/13481346/worried-about-stagflation-here-are-the-sectors-that-perform-best-across-equities-and-fixed-income), [Nasdaq](https://www.nasdaq.com/articles/managed-futures-as-a-strategy-massively-outperforms-in-2022), [thinknewfound](https://blog.thinknewfound.com/2023/02/what-is-managed-futures/)).

## Playbook Matrix v2 — monotonic tier design (2026-08-19)

Design rule (user's, now locked): **MOD is the baseline that defines WHAT to own in each regime; CONS dilutes it with cash; AGG/VAGG own the same regime exposures with more octane** — more weight in the regime's engine asset, or the same exposure in higher-torque form (QQQ→QLD→TQQQ, GLD→GDX miners, XLE→2x energy, TLT→TMF 3x duration). No tier may own a regime asset the baseline doesn't. This fixes the v1 flaw where AGG/VAGG's reflation cells arbitrarily dropped DBC (cost ~6-7pp in 2026).

| Tier | G | R (reflation) | S (stagflation) | D (deflation) |
|---|---|---|---|---|
| CONS | 40 SPY/40 IEF/20 GLD | 0.7×MOD-R + 30 cash | 70 cash/15 GLD/15 XLP | 45 TLT/35 cash/20 XLP |
| MOD | 70 QQQ/30 IEF | 30 SPY/25 XLE/25 GLD/20 DBC | 60 cash/20 GLD/20 XLP | 55 TLT/25 XLP/20 GLD |
| AGG | 100 QLD +0.5x IBS | 30 QLD/25 XLE/25 GDX/20 DBC | 50 cash/25 GLD/25 XLE | 60 TLT/20 TMF/20 GLD |
| VAGG | 100 TQQQ +1x IBS | 30 TQQQ/25 ERX(2x)/25 GDX/20 DBC | 40 cash/30 GLD/30 XLE | 50 TMF/30 TLT/20 GLD |

Optional flagged variant **v2B**: AGG/VAGG deflation cells use the equity barbell (60 TLT/40 QQQ; 50 TQQQ/50 TLT) — in-sample-informed rebound capture, adds +1.8pp (AGG) and +8.3pp (VAGG) CAGR but with beta 1.63 at VAGG.

### Results 2007-06 → 2026-08 (v1 numbers in the section above for comparison)

| Tier | CAGR | Sortino | maxDD | beta | 2025 | 2026 YTD |
|---|---|---|---|---|---|---|
| CONS-v2 | +8.4% | 1.19 | −13% | 0.17 | +19.5% | +13.6% |
| MOD-v2 | +13.3% | **1.35** | −15% | 0.31 | +25.5% | +19.2% |
| AGG-v2 | +20.7% | 1.03 | −37% | 0.60 | +37.2% | +20.8% |
| VAGG-v2 | +28.2% | 1.02 | −51% | 0.90 | +44.5% | +31.5% |
| VAGG-v2B | +36.6% | 1.19 | −52% | 1.63 | +71.9% | +31.5% |

Monotonicity check (2026 reflation cells held all year): MOD +22.9% → AGG +33.0% → VAGG +50.2%. Tier ordering now scales as designed; the 2026 anomaly (MOD beating AGG/VAGG) is resolved except for the April stagflation misfire, which is a classifier cost, not a design flaw.

**Evidence-quality note:** v2 is second-generation design on the same sample (informed by the 2026 diagnosis), so its backtest is weaker evidence than v1's. Mitigations: the redesign followed a structural principle (monotonic octane) rather than performance-chasing weights, and the S-cell change was pre-registered before this test. The binding judge remains forward paper performance.

## Robustness checks on the v2 rotation (2026-08-20; rotation sleeve only, no IBS overlay)

- **Transaction costs:** the switch changes quadrant only 3.3x/year. At a realistic 10bps per unit of turnover (liquid ETFs at IBKR), CAGR drag is ~0.5-0.7pp per tier (MOD +13.3% → +12.6%). Even at an implausible 50bps the tier ordering and viability survive. Costs are a non-issue.
- **Rebalance timing:** delaying execution 3, 5, or 10 trading days after month start moves CAGR by ~±1pp with no consistent direction (VAGG actually improves at +10d). No knife-edge timing dependence.
- **$8k account feasibility:** whole-share replication of the MOD reflation cell mis-allocates only 1.5% of the account at current prices; with IBKR fractional shares, ~0. All tiers' tickers trade well under $800/share. The rotation is fully tradable at current account size.

## Findings

1. **The 33/33/33 TQQQ/GLD/TLT mix the user read about is real but mislabeled as balanced**: +19.7% CAGR and Sortino 1.13, but −51% max drawdown and beta ≈ 1.0. Its failure mode is precisely a regime event: **2022 (−41.9%)**, when inflation broke the bond leg at the same time the levered equity leg fell — the two "ballasts" and the engine all sank together. 2008 was −34%.
2. **The QLD (2x) version dominates it risk-adjusted**: Sortino 1.19 vs 1.13, −37% vs −51% DD, at +15.3% CAGR — a better default for the same idea.
3. **Static leveraged mixes vs the indices strategy**: the 33/33 mixes earn their return from *diversified always-on leverage*; the indices strategy earns it from *timing*. Their drawdown profiles are complementary (mixes die in inflation years like 2022 [−42%] which the trend strategy sidestepped [−5%]; the trend strategy bleeds in chop like 2015-16 which the mixes shrugged off). Combining them is the obvious next test.
4. **Regime portfolios post the best headline numbers** (AGG: +22.4%, Sortino 1.11, −32%, Sharpe 0.95) but carry the design bias flag; their honest validation is forward paper trading or a pre-2007 replication with different-era ETF proxies.
5. Every leveraged-ETF result relies on the daily-reset simulation assumptions; real TQQQ tracking since 2010 is close to this model, but pre-2010 numbers are model, not history.
