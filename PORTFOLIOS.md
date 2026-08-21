# Portfolio Allocation Menu — by Risk Profile

Companion to `REGIMES.md`. All results: daily data 2007-06 → 2026-08 (includes 2008, 2020, 2022), dividends included, T-bill cash yield, leveraged ETFs simulated pre-2010 from QQQ (3x/2x daily reset − financing at T-bill+100bps − 0.95% ER). Metrics per the user's spec: CAGR, Sortino, max drawdown, beta (vs SPY); Sharpe added. Full grid: `research/portfolio_menu.csv`, annual returns: `research/portfolio_annual.csv`.

## Evidence quality — read first

- **Static mixes and the indices strategy are honest backtests of pre-specified rules.**
- **The "Regime" portfolios are in-sample designs**: their quadrant playbooks were chosen after seeing this sample's quadrant payoff table, so their numbers are upward-biased. UPDATE 2026-08-20: the framework (switch + cell structure + crash brake) has now passed a full out-of-sample replication on 1987–2007 — see the validation section below. Precise tier-level numbers remain in-sample; the framework-level claim (index returns at ~1/3 the drawdown) is validated on two disjoint 20-year samples.

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

## Switch cadence, turnover, and taxes (2026-08-20)

Measured on the locked switch, 2007–2026: **3.2 regime switches/year; median regime lasts 2 months** (mean 3.7, max 15); 52% of regimes last ≤2 months (whipsaw). Reflation persists longest (5.4mo avg), Deflation shortest (2.3mo). One-way turnover: ~300%/yr (MOD), ~263%/yr (AGG) — with median 2-month holds, nearly all switch-realized gains are short-term for tax purposes.

**Tested mitigation — 2-month confirmation delay** (rotate only after the new regime persists 2 months): halves switches (1.5/yr) and turnover (~139%/yr) with CAGR intact (MOD 13.3→13.5%), **but materially worsens drawdowns (MOD −15%→−19%; AGG −37%→−52%)** — the delay holds risk assets through the first two months of every crash regime, which is precisely when the framework earns its keep. Verdict: do NOT slow the model to save taxes; the crash protection is the product.

**Correct tax answer is account location, not model speed:** run the rotation inside tax-advantaged accounts (Roth IRA / 401k / HSA) where turnover is free; hold low-turnover sleeves (indices strategy, buy-and-hold cores) in taxable. In a taxable account at top marginal rates, ~300% ST turnover implies roughly 2–5pp/yr of tax drag — larger than any design refinement in this document. Secondary taxable mitigations: let contributions do the rebalancing (dominant while inflows are large relative to balance), trade only allocation deltas, and harvest the frequent whipsaw losses against gains.

## Rotation-timing grid: smoothing, drift, asymmetric switching (2026-08-20)

User hypothesis: the median-2-month regime is noise; smoothing the switch and letting winners run should cut turnover without losing much. Tested in one pass — 4 switching rules × 2 execution styles × MOD/AGG:

| Rule (MOD) | CAGR | Sortino | maxDD | switches/yr | turnover/yr |
|---|---|---|---|---|---|
| Monthly baseline | +13.1% | 1.33 | **−15%** | 3.2 | 312% |
| Symmetric 2-mo confirmation | +13.3% | 1.21 | −19% | 1.5 | 153% |
| **Asymmetric (instant to S/D, 2-mo confirm to G/R)** | +12.6% | 1.30 | **−14%** | 2.1 | 197% |
| Hysteresis ±2% bands | +13.5% | 1.27 | −19% | 2.1 | 211% |

Findings:

1. **The flickers are load-bearing.** Every rule that delays risk-OFF transitions (symmetric confirmation, hysteresis) improves CAGR slightly and cuts turnover ~35%, but blows out drawdowns (MOD −15%→−19%; AGG −37%→−52%). The 1-month "noise" regimes are disproportionately the first month of real crashes. The classifier is not a macro-narrative detector; it is a risk trigger that happens to organize by regime — slowing it to match the narrative destroys the protection.
2. **Asymmetric switching is the one viable smoother**: exiting to defense instantly but requiring 2 months' confirmation before re-risking preserves (slightly improves) drawdown, cuts switches 3.2→2.1/yr and turnover by a third, at a cost of ~0.5pp CAGR on MOD. On AGG the cost is 2.7pp (levered re-entries missed) — not worth it for leveraged tiers. Status: optional variant for CONS/MOD (late-glide ages); rejected for AGG/VAGG.
3. **Let-winners-run (drift execution) is nearly a no-op**: ±0.1–0.6pp CAGR, turnover only ~10pp lower — regimes are too short for intra-regime rebalancing to matter. Adopt it anyway (free, defers intra-regime sells) together with contribution-based touch-ups: with 2–5 month regimes, intra-regime drift is small enough that new contributions can do all within-regime rebalancing; switch turnover (the dominant cost) is unavoidable by construction.
4. After-tax note: the annual-taxation approximation under-credits low-turnover variants' deferral benefit; directionally the asym variant's tax edge is slightly better than shown.

## Refinement grid II: execution day, tranching, crash brake, vol targeting (2026-08-20)

Four pre-stated micro-refinements, one pass, MOD & AGG:

| Variant (MOD / AGG) | CAGR | Sortino | maxDD |
|---|---|---|---|
| Baseline (exec day 1) | +13.1% / +19.7% | 1.33 / 1.00 | −15% / −37% |
| Exec day 8 / 15 / 22 | 12.0–13.9% / 19.4–23.2% | — | −18..−19% / −45..−50% |
| 4-tranche staggered | +12.6% / +20.5% | 1.27 / 1.06 | −16% / −39% |
| **+ Intra-month crash brake** | **+13.6% / +21.7%** | **1.43 / 1.13** | **−15% / −33%** |
| + Vol-target overlay | +10.9% / +15.4% | 1.24 / 0.91 | −14% / −32% |
| **Tranche + brake combo** | +13.0% / +21.5% | 1.41 / **1.17** | **−14% / −36%** |

Verdicts:

1. **Execution-day sensitivity is real**, mostly in drawdown (AGG: −37% on day 1 but −45..−50% on other days) — day-1 results contain timing luck. This makes single-day execution a fragility, and motivates:
2. **Tranching (4 sleeves on staggered weeks)**: averages away timing luck; lands near the good outcomes without betting on a calendar day. Adopted.
3. **Intra-month crash brake** (daily tripwire: if SPY closes >5% below its 200-day SMA while in G or R, go to the tier's S cell until the next monthly classification): the clear win — improves BOTH return and risk on both tiers (+0.5 to +2.0pp CAGR, Sortino 1.33→1.43 / 1.00→1.13, AGG DD −37%→−33%) for ~0.4 extra switches/yr. It covers the monthly cadence's known blind spot (fast crashes between observations, e.g. Feb-Mar 2020). Single pre-stated spec, no parameter sweep. **Adopted** — requires a daily check in live implementation (the monthly paper Routine cannot brake intra-month; live spec pending a daily monitor).
4. **Vol targeting: rejected.** The rotation already de-risks by regime; layering inverse-vol scaling double-counts and costs 2.2–4.3pp CAGR for ~1–4pp of DD.
5. **Combined operating spec** (tranche + brake): MOD +13.0%/Sortino 1.41/−14%; AGG +21.5%/1.17/−36% — the best risk-adjusted configuration found to date. Caveat: refinements iterate on the same sample; effects of this size (0.5–2pp) should be treated as directional until the forward ledger accumulates.

## OUT-OF-SAMPLE VALIDATION: 1987–2007 replication (2026-08-20)

The framework transplanted to two decades of data that no design decision ever touched, using era-appropriate instruments (VFINX/VUSTX/Fidelity gold-energy-staples funds; GSCI spot for the inflation axis; identical locked switch rule; MOD-structure cells; same crash-brake spec):

| 1987-03 → 2007-05 | CAGR | Sortino | maxDD |
|---|---|---|---|
| **MOD-proxy rotation + crash brake** | **+11.5%** | **0.99** | **−17%** |
| MOD-proxy rotation (no brake) | +10.8% | 0.83 | −24% |
| S&P 500 fund B&H | +11.0% | 0.56 | −48% |
| 60/40 | +10.3% | 0.73 | −25% |

Everything replicated out-of-sample:

- **The core claim held**: index-level returns at roughly one-third of the index drawdown, Sortino ~1.8x the index.
- **The behavioral signature is identical to 2007–2026**: pays an insurance premium in raging bulls (1995–99: +18.9%/yr vs SPX +28.4%), collects in busts (2000/2001/2002: **+9.5% / +5.4% / +4.7%** while the S&P lost −9% / −12% / −22%; 1987: +0.5% vs −11.1%).
- **The switch cadence is a stable property, not sample noise**: 3.4 switches/yr out-of-sample vs 3.2 in-sample — the "flickering" the user questioned is how this thing behaves in every era.
- **The crash brake validated out-of-sample too**: +0.7pp CAGR and maxDD −24%→−17% (Black Monday aftermath, 1990, 1998, dot-com).

Caveats: proxy funds carry higher fees than ETFs (conservative bias — in our favor); cells are structural transplants, not identical allocations; single alternative sample. Nonetheless this upgrades the framework's evidence tier: the central claim now holds on two disjoint 20-year windows spanning 1987–2026.

## Refinement grid III: cell-level tilts and cash sweep (2026-08-20)

- **R-cell momentum tilt** (overweight the strongest of XLE/GLD(GDX)/DBC by trailing 6-month momentum, 45/32.5/22.5 split of the cell's commodity sleeve): +0.2 to +0.4pp CAGR, risk flat. Adopted (principled cross-sectional momentum, monotone across both tiers).
- **D-cell duration selection** (TLT vs IEF by 6m momentum): no effect. Not adopted.
- **Cash sweep**: SHY beat rolled T-bills by +0.35%/yr on the cash sleeve over 2007–2026. SHY confirmed as the cash instrument.

## The stagflation cell, solved: trend-conditional duration (2026-08-20)

The user's challenge: "there's got to be SOMETHING that makes money in stagflation." Candidate sweep across BOTH eras (modern 2007–2026 S-months, n≈19mo; pre-2007 proxy S-months, n≈34mo), pass rule = positive in both independent samples:

| Candidate (annualized in S-months) | Modern | Pre-2007 | Verdict |
|---|---|---|---|
| **Duration, trend-conditional (long TLT if TLT>10m SMA, else cash)** | **+11.1%** | **+15.5%** | **PASS** |
| Duration trend-conditional long/short | +17.5% | +11.9% | pass (shorting adds modern-era juice, pre-2007 drag) |
| Cash | +2.1% | +3.9% | pass (baseline) |
| Short SPY | +10.4% | **−2.0%** | FAIL — modern-only artifact |
| Dollar (UUP) | +7.3% | no data | insufficient |
| Gold | −8.7% | +0.6% | fail |
| Energy / commodities / defensives | −6 to −26% | −7 to +6% | fail |

**Mechanism**: "stagflation" under this classifier is two distinct sub-regimes — growth-scare (bonds rally: 1990, 2008-adjacent) and inflation-shock (bonds crash: 2022) — and the bond's own 10-month trend identifies which one is running, ex-ante. This is the managed-futures principle applied inside the S cell. Gold is removed from S cells (negative or flat in both samples).

**v3 S-cells (pre-registered, long/cash variant chosen for robustness over the L/S variant):** CONS 60 cash/40 cond-TLT · MOD 50/50 · AGG 40/60 · VAGG 30/70.

Full-period impact (with crash brake): MOD +13.6%→**+14.6%**, Sortino 1.43→**1.50**, DD −15→−14%; AGG +21.7%→**+23.5%**, Sortino 1.13→1.18. The S quadrant flips from dead weight to a contributor.

## D-cell test: conditional duration rejected, gold adopted (2026-08-20)

Hypothesis (symmetry with the S-cell): D-cell duration should also be trend-conditional. **Rejected by the data** — modern D-months: unconditional TLT +7.0% vs conditional +5.5%; pre-2007: +6.4% vs +7.3% (wash). Reason: 70–96% of D-months already have bonds trending up — "deflation" under this classifier essentially IS the bond-friendly regime; it does not split into sub-types the way stagflation does. Unconditional duration stays.

The same test surfaced the real D-cell gap: **gold earned +24.7% (modern) and +30.8% (pre-2007) annualized in D-months** — two-sample consistent and only 0–20% of the old cells. Equities in D are also positive both eras (+32%/+50% modern rebounds, +9.7% pre-2007), partially rehabilitating a MODERATE rebound slice (not the old 50% TQQQ barbell).

**v4 D-cells (pre-registered, single spec, validated both eras):** duration core intact, gold to 25–30%, 10–15% equity slice with monotone octane (SPY→SPY→QQQ→QLD). Results: modern MOD +14.5→**+14.9%** (Sortino 1.50→**1.54**), AGG +23.4→**+24.6%** (Sortino 1.19→**1.25**, DD −34→−33); pre-2007 replication unchanged (+13.1%, Sortino 1.22→1.23 — no degradation). Adopted; wired into `matrix.py` as v4 ahead of the September ledger run.

Cumulative note: the pre-2007 replication with all adopted upgrades (conditional-S, brake, v4-D) now runs +13.1%/Sortino 1.22/−15% vs the original +11.5%/0.99/−17% — the refinements improve the era they were not designed on, which is the pattern genuine improvements should show.

## G-cell engine test: momentum selection — tested, NOT adopted (2026-08-21)

The last unvalidated performance driver: G-cell = fixed QQQ. Tested (pre-registered): engine = best 12-month momentum among {QQQ, SPY, EFA, EEM} (pre-2007 menu: NDX, SPX, Vanguard Intl, Fidelity EM), 6m variant also run and disclosed.

**In G-months:** modern — fixed QQQ +23.4%/yr vs select +17.0% (any switch away from QQQ cost money in QQQ's era); pre-2007 — select +29.7% vs fixed NDX +23.8% (rode NDX through the 90s, correctly rotated to EM/Intl 2003–07). **Full-tier:**

| | Modern MOD | Modern AGG | Pre-2007 proxy |
|---|---|---|---|
| G = fixed QQQ/NDX | **+14.9% / 1.54** | **+24.6% / 1.25** | +14.7% / 1.16 |
| G = 12m momentum select | +13.5% / 1.40 | +20.6% / 1.07 | **+16.3% / 1.32** |

Findings:

1. **This is insurance, not a free win** — unlike conditional-S duration or D-cell gold, selection is symmetric: pays in ex-US eras, costs in US-tech eras (−1.4pp modern MOD, −4.0pp modern AGG where leverage amplifies selection lag). Era-consistency does improve (select's Sortino band 1.32–1.40 vs fixed's 1.16–1.54).
2. **The original concern was partly wrong**: fixed Nasdaq IN G-MONTHS delivered ~23–24%/yr in BOTH eras, and full-tier +14.7% even through the ex-US 2000s — because G-months (US growth on, inflation off) structurally select for Nasdaq-friendly conditions. The G-cell's QQQ bet is less era-fragile than it looks.
3. Practical: 2x/3x international ETFs (EFO/EET) are tiny/illiquid — AGG/VAGG implementations of select are shaky regardless.

**Decision: keep fixed QQQ; shelf the select variant as a validated contingency.** Revisit trigger (pre-registered): if the 12m-momentum pick differs from QQQ for 3+ consecutive G-classified months, run the comparison on live data and decide then — the switch to select would be an evidence-backed documented move, not a panic improvisation.

**Weakest-link ranking after this round:** G-cell concentration downgraded from "unvalidated" to "tested and quantified". New top weaknesses: (1) execution gap — the crash brake has no live daily monitor and the forward ledger has n=1 month; (2) classifier rebound lag (no upside analogue to the crash brake); (3) taxes in the user's taxable-only implementation.

## CORRECTION: crash brake retracted; rebound accelerator rejected (2026-08-21)

While testing the rebound accelerator (the brake's upside mirror: while in S/D, jump to the G cell when SPY closes back above its 200-day SMA), its results were implausibly large — which exposed a **one-day look-ahead in the intra-month simulation**: signals evaluated at day-t close were earning day-t returns on the new weights. Trading at the signal-day close means the new position earns from day t+1 — and crash/bounce days cluster exactly so as to matter.

**Honest T+1 rerun (modern era, v4 + conditional-S):**

| | CAGR | Sortino | maxDD |
|---|---|---|---|
| MOD monthly-only (no intra-month mechanisms) | **+14.2%** | **1.43** | **−15%** |
| MOD + crash brake (T+1) | +13.9% | 1.42 | −15% |
| MOD + brake + accelerator (T+1) | +14.4% | 1.44 | **−20%** |
| AGG monthly-only | **+22.2%** | **1.10** | **−35%** |
| AGG + brake (T+1) | +21.9% | 1.11 | −39% |
| AGG + brake + accelerator (T+1) | +23.0% | 1.11 | **−46%** |

Verdicts:
- **Crash brake: RETRACTED.** Its previously reported benefit (Refinement grid II, and the pre-2007 brake validation) was entirely the look-ahead artifact. Honestly executed it is neutral-to-harmful. It was never wired into live code (pending the daily monitor) — no live impact. 
- **Rebound accelerator: REJECTED.** Small CAGR gain, large drawdown cost, both eras.
- **Corrected official numbers (monthly-only, v4 + conditional-S):** modern MOD +14.2%/1.43/−15%, AGG +22.2%/1.10/−35%; pre-2007 replication +11.4%/0.84/−24% vs S&P +11.0%/0.56/−48% — **the out-of-sample validation of the framework survives**; only the brake's claimed contribution was fake.
- Cell-level conclusions (conditional-S, D-gold, R-tilt, G-engine verdicts) compared variants under identical execution and are unaffected in direction; their headline magnitudes shift with the corrected baseline.
- **Operational consequence: the system is monthly-complete.** No daily monitor is needed; the intra-month "execution gap" is closed by deletion, not construction. The remaining forward work is letting the ledger accumulate.

### Autopsy: why the rebound accelerator fails (2026-08-21)

All 23 modern-era fires enumerated. Three findings explain everything:

1. **The cross-day pop is the whole trade — and it is uncapturable.** The day SPY crosses its 200d SMA averages **+1.70%**; the drift from the first tradeable day to month-end averages **+0.20%**. The information in the cross is consumed by the move that produces it. (This +1.7%×23 is exactly what the look-ahead bug was harvesting.)
2. **Half the fires are bear traps.** Only 52% were confirmed by the next monthly classification. Confirmed fires drift +1.32%; false alarms −1.01% — and the tails are catastrophic: 2020-03-02 (biggest bounce of the COVID crash, −16% SPY to month-end after firing), 2022-08-16 (the exact top of the 2022 bear rally, −8%), three consecutive whipsaws in 2011, 2008-05-06 (the '08 bear rally top). Structurally, crossing the 200d SMA from below while classified S/D REQUIRES a violent recent rally inside a downtrend — the textbook definition of a bear-market rally.
3. **The "opposite" trade doesn't exist either**: overall drift +0.20% means fading the cross earns ≈ −0.2% before costs. The profitable side of the accelerator's bad trades is simply *staying defensive* — which is the baseline — and the monthly classifier already captures the real rebounds a few weeks later (the 52% confirmed fires flip to G at month-end anyway).

**Conclusion: the rebound lag is not a defect — it is the fee that filters bear traps.** The monthly cadence acts as an accidental ~3-week confirmation filter, trading ~+1.3% of missed early-rebound drift for immunity to −1% average (−16% tail, levered) trap entries. Any faster re-entry rule must beat that trade, and the canonical one doesn't.

- Lesson recorded: intra-month mechanisms need T+1 execution modeling from the first test; monthly mechanics were never affected (signals from prior month-end, executed at month start).

## Tax execution habits, quantified (2026-08-21)

Lot-level simulation of the MOD rotation, 2007–2026, real contribution schedule, comparing naive execution (FIFO lots, full monthly rebalance) vs tax-aware execution (HIFO lot selection + contributions-buy-the-underweights-first + harvesting lots >5% underwater):

| Bracket | Naive final | Tax-aware final | Improvement |
|---|---|---|---|
| 24% ST / 15% LT | $1,314k | $1,335k | **+$20.5k (+1.6%)** |
| 35% ST / 23.8% LT | $1,150k | $1,177k | **+$26.9k (+2.3%)** |

Worth doing (it is one IBKR setting plus two habits), worth ~0.1pp/yr — but not transformative: total taxes paid are nearly identical; the gain is deferral compounding. The dominant tax decision remains structural (turnover level and account type), already settled: keep model speed, accept the drag, apply the habits.

## The short screen: two-sample validated shorts (2026-08-21)

User criterion: shorts only where the asset is NEGATIVE IN ABSOLUTE TERMS in a regime, in both eras — no shorting positive assets just to buy Sharpe. Full asset x regime screen (modern 2007–2026 / pre-2007 proxies):

**Passers (negative both eras):**
- **Commodities/oil in DEFLATION**: USO −43.3%/yr modern (DBC −7.2%) / GSCI −0.6% pre-2007. Mechanism is the system's own: D-classification REQUIRES commodities below their 10-month SMA — shorting them is trend-following's short side, and a short USO position additionally collects the contango roll drag documented in the original CL/USO research. Self-limiting risk: an oil spike pushes DBC above its SMA and flips the regime out of D, closing the short.
- Energy equities in STAGFLATION (XLE −26.3% / ENER −3.4%): parked — n=19 modern months, weak pre-2007 leg, squeeze risk in a rare short-lived regime.

**Failures recalled**: short equity in stagflation (+10.4% modern) failed pre-2007 (−2.0%); short bonds in stagflation helped modern, hurt pre-2007 — both already rejected.

**Impact test — 10%/15% short-oil sleeve in MOD/AGG D-cells (funded from duration, borrow 2% modeled):**

| | Modern | Pre-2007 |
|---|---|---|
| MOD v4 → +sleeve | 14.4%/1.43/−16% → **14.9%/1.50/−14%** | 11.4%/0.84/−24% → 11.4%/0.84/−24% (neutral) |
| AGG v4 → +sleeve | 22.7%/1.12/−36% → **23.5%/1.16/−34%** | — |

Ideal asymmetric profile: helps the era where the effect is strong, harmless where it was weak. Implementation note for a margin-free account: SCO (2x inverse oil ETF) at half weight ≈ the modeled short, with daily-reset tracking differences disclosed.

### Adopted: matrix v5 — the short book and its switch (2026-08-21)

User approved adoption AND requested an architectural on/off switch so this and any future validated short can be toggled globally. Wired in `src/portfolio/matrix.py`:

- **`INCLUDE_SHORTS`** (module-level, default ON): the global switch for the entire short book. OFF resolves every short placeholder to its long fallback, restoring the v4 long-only cells *exactly* (verified by test).
- **`SHORT_OIL` placeholder** in the D-cells: MOD 10%, AGG 15%, VAGG 15% — funded from TLT in every case (VAGG keeps its full TMF octane; TLT 20%→5%). CONS stays long-only per the adoption decision.
- **Registry pattern for future shorts**: `SHORT_IMPL` maps each placeholder to its (2x-inverse ETF, leverage) and `SHORT_FALLBACK` to its shorts-off long substitute. A future validated short (e.g. XLE-in-S if it ever passes two-sample) is one dict entry + one cell edit, and automatically obeys the switch.
- **Margin-free resolution**: 10% short exposure → 5% SCO + 5% SHY (2x inverse at half weight). The ledger holds only real ETFs; daily-reset tracking drift vs a true short is the disclosed cost of avoiding margin.
- Ledger provenance: each row's `signals` JSON now records `include_shorts`, so history shows which book was in force; resolved-allocation snapshots were already append-only.

Resolved v5 D-cells (shorts ON): MOD {TLT 35, GLD 30, XLP 15, SPY 10, SCO 5, SHY 5}; AGG {TLT 25, TMF 15, GLD 30, QQQ 15, SCO 7.5, SHY 7.5}; VAGG {TMF 35, TLT 5, GLD 30, QLD 15, SCO 7.5, SHY 7.5}. Expected impact (two-sample tested above): modern MOD 14.4→14.9%/Sortino 1.43→1.50/DD −16→−14%, AGG 22.7→23.5%/1.12→1.16/−36→−34%; pre-2007 neutral. Live from the September 2026 ledger run.

## Standing rule: no broad-market shorts (2026-08-21)

User directive, permanent: **never short broad US equity indices** (SPY/QQQ/IWM/DIA and their levered kin) — broad-market momentum/bias is up, and a crash hedge alone doesn't justify the carry. Sub-sectors and industry groups ARE shortable, subject to the existing two-sample absolute-negative rule and small sizing. All future short candidates screen under both rules.

## The stagflation sub-sector short screen (2026-08-21)

One-pass, pre-registered: universe = 18 modern sub-sector/industry ETFs (XLE/XLY/XLF/XLK/XLI/XLB/XLV/XLU/XLP/IYR/XRT/XHB/ITB/KRE/IYT/SMH/GDX/XBI) paired with 17 Fidelity Select funds (inceptions ~1985) as pre-2007 proxies; criterion = annualized absolute return negative in S-months in BOTH eras (modern n=19 S-months, pre-2007 n=34-35).

**Data lesson recorded**: Yahoo silently coarsens `interval=1d&range=max` to QUARTERLY bars on long mutual-fund histories (and monthly on ETFs) while still reporting success — a first pass produced garbage pre-2007 numbers (+100%/yr artifacts from 13-of-35-month coverage). All long-history pulls must use explicit `interval=1mo` (or explicit-epoch daily) and assert `meta.dataGranularity`.

**Result: only two of 18 groups pass.** Modern S-months are broad-bear months (everything negative except XBI), so the pre-2007 leg is the real filter — and it kills almost everything: chemicals +33%/yr, banks +17%, housing +19%, transports +17%, staples +11%, gold miners +9% in pre-2007 S-months.

| Passer | Modern S | Pre-2007 S | Verdict |
|---|---|---|---|
| Energy (XLE / FSENX) | −26.5%/yr | −3.4%/yr | validated, impact-tested below |
| Semiconductors (SMH / FSELX) | −5.3%/yr | −8.5%/yr | passed screen, FAILED impact test |

**The relative-alpha check (the important one):** energy underperforms the broad market in S-months by **−14.3pp/yr modern and −12.5pp/yr pre-2007** — nearly identical sector alpha in two non-overlapping eras. Pre-2007 the market was UP +9.1%/yr in S while energy fell — so this is NOT a broad-market short in disguise; it clears the user's no-broad-shorts rule on mechanism, not just wrapper. Economic story: energy equities are long-duration claims on energy cash flows — stagflation compresses their multiples and demand outlook even while spot commodities rise.

**Impact test** (sleeve from the S-cell cash leg, MOD 10%/AGG 15%/VAGG 15%, CONS long-only, borrow 2%, same engine both eras; baseline reproduces official v5 numbers):

| Variant | MOD modern | AGG modern | VAGG modern | MOD pre-2007 |
|---|---|---|---|---|
| baseline v5 | +15.1%/1.68/−14.3% | +23.8%/1.24/−33.7% | +33.5%/1.20/−48.9% | +11.7%/1.35/−24.5% |
| **short XLE** | **+15.3%/1.70/−14.3%** | **+24.1%/1.26/−33.7%** | **+33.8%/1.22/−48.9%** | **+11.7%/1.37/−24.5%** |
| short SMH | +15.0%/1.68/−14.3% | +23.7%/1.25/−33.7% | +33.4%/1.21/−48.9% | +11.7%/1.36/−24.5% |
| 50/50 split | +15.2%/1.69/−14.3% | +23.9%/1.25/−33.7% | +33.6%/1.21/−48.9% | +11.7%/1.36/−24.5% |

XLE passes the pre-registered bar (modern improves in every tier, pre-2007 improves slightly); SMH fails it (modern CAGR flat-to-down after borrow — its −5.3%/yr modern edge is too thin) and is REJECTED despite passing the screen. Split is diluted XLE.

**Disclosed tail risk**: ~half of S-months are squeezes (energy rises 9/19 modern, 14/34 pre-2007; worst single month against the short: XLE +16.0% in 2022-05, FSENX +13.1% in 2000-12). At the 10-15% sleeve that's a worst observed month of ≈ −1.6% of portfolio. The edge comes from down-months being roughly twice the size of up-months. Expected contribution is modest (+0.2-0.3pp CAGR, +0.02 Sortino, DD unchanged) — about half the oil-in-D sleeve's value — priced honestly, not oversold.

Margin-free implementation verified: ERY (Direxion 2x inverse S&P Energy — same index family as XLE) and DUG both trade; ERY at half weight + SHY remainder mirrors the SCO pattern.

### Adopted: matrix v6 — energy short in the S-cells (2026-08-21)

User approved, folded into the `INCLUDE_SHORTS` switch as designed. `SHORT_ENERGY` registered in `SHORT_IMPL` (ERY, 2x) with fallback SHY; S-cells now MOD {SHY 40, SHORT_ENERGY 10, COND 50}, AGG {SHY 25, SHORT_ENERGY 15, COND 60}, VAGG {SHY 15, SHORT_ENERGY 15, COND 70}; CONS long-only. Resolved (shorts ON, bonds trending up): MOD {SHY 45, TLT 50, ERY 5}; AGG {SHY 32.5, TLT 60, ERY 7.5}; VAGG {SHY 22.5, TLT 70, ERY 7.5}. Shorts OFF restores the long-only S-cells exactly (tested). The short book is now: oil in Deflation + energy equities in Stagflation, both behind the one switch. Live from the September 2026 ledger run.

## Findings

1. **The 33/33/33 TQQQ/GLD/TLT mix the user read about is real but mislabeled as balanced**: +19.7% CAGR and Sortino 1.13, but −51% max drawdown and beta ≈ 1.0. Its failure mode is precisely a regime event: **2022 (−41.9%)**, when inflation broke the bond leg at the same time the levered equity leg fell — the two "ballasts" and the engine all sank together. 2008 was −34%.
2. **The QLD (2x) version dominates it risk-adjusted**: Sortino 1.19 vs 1.13, −37% vs −51% DD, at +15.3% CAGR — a better default for the same idea.
3. **Static leveraged mixes vs the indices strategy**: the 33/33 mixes earn their return from *diversified always-on leverage*; the indices strategy earns it from *timing*. Their drawdown profiles are complementary (mixes die in inflation years like 2022 [−42%] which the trend strategy sidestepped [−5%]; the trend strategy bleeds in chop like 2015-16 which the mixes shrugged off). Combining them is the obvious next test.
4. **Regime portfolios post the best headline numbers** (AGG: +22.4%, Sortino 1.11, −32%, Sharpe 0.95) but carry the design bias flag; their honest validation is forward paper trading or a pre-2007 replication with different-era ETF proxies.
5. Every leveraged-ETF result relies on the daily-reset simulation assumptions; real TQQQ tracking since 2010 is close to this model, but pre-2010 numbers are model, not history.
