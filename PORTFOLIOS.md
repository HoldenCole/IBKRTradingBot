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

## The sub-sector LONG screen (2026-08-21)

User prompt: had we ever screened sub-sector longs — with the explicit warning that this is prime overfitting territory (tech looks unbeatable in cherry-picked windows). Answer: not systematically until now; the matrix's existing sector longs (XLE/GDX/DBC in R, XLP+GLD in D) each entered through their own two-era tests. Full grid run: same locked 18-group universe as the short screen (no additions after seeing data), all four quadrants, both eras, benchmarks (SPY/QQQ modern, VFINX/NDX pre-2007) printed first, full tables kept — the bar for a LONG is beating the cell's incumbent in both eras, not being positive.

**What the grid shows, cell by cell:**
- **G**: only semis beat the Nasdaq incumbent in both eras (SMH +27.9% vs QQQ +23.3% modern; FSELX +28.7% vs NDX +27.0% pre-2007). NOT adopted — the two eras are not independent evidence here: each contains a tech supercycle (1990s, 2010s-20s AI), so "semis beat QQQ" is the same bubble sampled twice, with margins (+4.6pp/+1.7pp) inside fund-noise range. AGG/VAGG already express G-aggression through QLD/TQQQ — leverage on 100 diversified names beats concentration in one industry at equal octane. Pre-2007's other QQQ-beaters (leisure, retail) collapse in the modern era — era instability on display.
- **R**: XLE is the grid's #1 modern sector (+16.8%) and top-tier pre-2007 (+14.6%) — the incumbent R-trio already owns the winner. Nothing beats it in both eras. (Noted: GDX's absolute in-regime R record is mediocre — +5.5%/+0.2% — but it sits behind the momentum tilt, which demotes it dynamically; the tilt was separately validated.)
- **S**: biotech is the only sector positive in S in both eras (XBI +14.8% modern, FBIOX +9.5% pre-2007) — REJECTED as the textbook false passer: no relative alpha pre-2007 (VFINX +9.1% — it merely matched the market), its own sector neighbor contradicts it (XLV −11.5% modern), n=19, and with 18 candidates screened, ~1 spurious two-sample "passer" is the expected base rate. Chemicals is the cautionary exhibit the user predicted: +33%/yr in pre-2007 S-months, −25%/yr modern.
- **D**: the one coherent multi-sector signal — early-cycle cyclicals (transports, retail, discretionary, materials) beat the broad market in D-months in BOTH eras (one mechanism, many expressions: the D rebound is early-cycle). And miners dwarf everything (GDX +70.5%/yr modern D; FSAGX +55.1% pre-2007).

**Impact tests (same engine, baseline reproduces official v6):**

| Variant | CONS | MOD | AGG | VAGG | MOD pre-2007 |
|---|---|---|---|---|---|
| baseline v6 | +9.7%/1.58/−10.2% | +15.3%/1.70/−14.3% | +24.1%/1.26/−33.7% | +33.8%/1.22/−48.9% | +11.7%/1.37/−24.5% |
| D rebound slice → IYT/XRT/XLY basket | +9.8%/1.61/−10.9% | +15.4%/1.71/−14.3% | +24.0%/1.26/−33.8% | — | +11.8%/1.38/−24.5% |
| **AGG/VAGG D gold: GLD → GDX** | unchanged | unchanged | **+26.3%/1.33/−34.3%** | **+36.1%/1.27/−49.3%** | unchanged |

- **Rebound-basket: REJECTED.** +0.1pp with a deeper CONS drawdown — the broad-market slice already captures the early-cycle bounce; slicing it finer adds noise, not signal.
- **GDX-for-GLD in AGG/VAGG D-cells: validated candidate with a disclosed asterisk.** +2.2pp CAGR AND +0.06 Sortino at AGG (so not mere vol-loading), +2.3pp/+0.05 at VAGG, DD −0.4/−0.6pp deeper. The asterisk: this is the one candidate the two-sample rule cannot fully bless — the pre-2007 gold proxy (FKRCX) is itself a miners fund, so the older era can't distinguish bullion from miners (it does confirm miners-in-D worked pre-2007: FSAGX +55%/yr in D-months). Design coherence argues for it: AGG/VAGG are the octane tiers whose rule is "same asset, levered expression" (TLT→TMF, QQQ→QLD) — miners ARE levered gold, and MOD keeps bullion, preserving monotonicity. Status: **REJECTED by user decision (2026-08-21): "Just leave gold."** Bullion stays in every D-cell. The incomplete two-sample leg was the deciding weakness; the candidate is recorded here should the forward ledger ever motivate revisiting it.

## Workbook refresh to matrix v6 (2026-08-21)

GrowthProjection.xlsx regenerated from the v6 engine. Convention check passed first: the engine's SPY row reproduces the stored benchmark row to 4 decimals (CAGR .1082/.1082, Sortino .6728/.6728, maxDD −.5519/−.5519), so tier rows and benchmark rows remain computed under one identical method — no asymmetric treatment. Updated tier headline rows (Jun 2007–Aug 2026, shorts ON):

| Tier | CAGR | Sortino | maxDD | beta | 2008 | 2022 |
|---|---|---|---|---|---|---|
| CONS | +9.7% | 1.60 | −10.2% | 0.17 | +13.8% | +1.9% |
| MOD | +15.3% | 1.73 | −14.3% | 0.28 | **+20.7%** | +0.0% |
| AGG | +24.1% | 1.22 | −33.7% | 0.59 | +38.0% | −25.3% |
| VAGG | +33.8% | 1.12 | −48.9% | 1.00 | +46.3% | −31.2% |

The short book shows up exactly where designed: MOD's 2008 rises to +20.7% (oil short in the deflation legs, energy short in the stagflation legs of the crash year). Per-regime monthly means in the Data sheet updated (MOD: S-cell 0.46→0.65%/mo, D-cell 1.45→1.78%/mo); regime frequencies/durations unchanged (classifier untouched). Haircut, tax engine, contribution schedule, glide path, and benchmark rows all unchanged.

## Version history: per-quadrant returns, v1 → v6 (2026-08-21)

All six matrix versions re-run through ONE identical engine (rotation sleeve only, no IBS overlay, no retracted brake; monthly rotation, ex-ante signals; Jun 2007–Aug 2026; shorts as live SCO/ERY implementation). Cross-check: v1/v2 reproduce their originally recorded results; v6 reproduces the current official numbers. Annualized return INSIDE each quadrant's months:

**Growth** — unchanged v1→v6 (CONS +8.9 / MOD +17.5 / AGG +42.6 / VAGG +61.4%): the G-cells were never altered; momentum-selection was tested and rejected.

**Reflation** — CONS +8.2→9.8, MOD +12.5→13.1, AGG +13.6→14.2, VAGG +15.1→20.3%: v2 restored DBC + octane instruments (VAGG +5pp), v3's momentum tilt added the rest.

**Stagflation** (the transformation): CONS −2.1→+4.8, MOD −8.3→+7.7, AGG −11.1→+9.5, VAGG −15.2→+10.3%. v2 stripped the canon energy/gold cells (still negative), v3's trend-conditional duration flipped every tier positive, v6's energy short added +2.2-3.3pp.

**Deflation**: CONS +9.3→14.2, MOD +15.5→22.5, AGG +25.8→26.9, VAGG +81.4→37.1%. The VAGG path tells the honesty story: v1's +81%/yr was the flagged in-sample TQQQ barbell; v2 deleted it on principle (down to +11.8%), v4 rebuilt the cell from two-era-validated parts (gold 30% + QLD rebound slice, +31.0%), v5's oil short finished it (+37.1%) — better risk-adjusted than v1's in-sample artifact, and earned honestly.

**Full-period by version** (CAGR/Sortino/maxDD): v1 MOD 12.6/1.40/−15, VAGG 33.0/1.09/−57 → v2 13.3/1.53/−15, 28.3/0.93/−53 (honesty cost: VAGG −4.7pp) → v3 14.2/1.59, 30.0/0.97 → v4 14.6/1.64/−16, 32.7/1.07/−51 → v5 15.1/1.71/−14, 33.5/1.10/−49 → v6 15.3/1.73/−14, 33.8/1.12/−49. VAGG only re-passed v1's headline CAGR at v5 — but with 8pp less drawdown and higher Sortino; every version's gain after v2 came from a two-era-validated component, not from re-fitting the sample.

Evidence-quality reminder: v3+ refinements were designed after seeing the modern sample (each validated on 1987-2007 as mitigation); the forward ledger remains the binding judge.

## Mid-regime entry analysis (2026-08-21)

User question: what's the logic for entering mid-regime (market extended, oil already up, rates rising)? Empirics, MOD v6, 2007–2026, monthly returns conditioned on the AGE of the regime being held: month 1 +1.01%/mo, month 2 +1.86%, months 3-4 +1.56%, months 5-8 +1.19%, month 9+ +0.54% — decay with age, but NO age bucket is negative. Reflation specifically at month 6+ (the current situation): MOD +0.97%/mo with 63% positive months, while SPY in those same months averaged −0.05% — the R-book's commodity/gold/energy construction carries late-reflation even when equities stall. Random-entry stress: all 225 six-month entry windows since 2007 — 84% positive, mean +7.6%, worst −7.2%. Conclusion: mid-regime entry costs expected return relative to early entry but has never been a structurally bad trade; the whole-period record already contains every top. Contributions (large relative to account) provide natural averaging; tranching remains available for lump sums.

## Crypto screen (2026-08-21)

User question: did we ever consider crypto? Screened BTC (2014+) and ETH (2017+) through the quadrant framework — necessarily ONE-ERA (no pre-2014 data exists), which already fails the two-sample rule by construction. What the one era shows:

| In-regime ann. | G | R | S | D | 2022 | maxDD | corr QQQ (2020+) | corr GLD |
|---|---|---|---|---|---|---|---|---|
| BTC | +83% (n=52) | +49% | **−33% (n=9)** | +84% (n=15) | −65% | −74% | 0.47 | 0.10 |
| ETH | +85% | +4% | −46% | +36% | — | worse | — | — |

Verdicts:
1. **"Digital gold" is empirically false in this data**: BTC's gold correlation is ~0.05-0.10 while its equity correlation is ~0.5 (2020+). In stagflation — where a real store-of-value earns — BTC lost 33%/yr; in 2022 (the one inflation-shock test it has ever faced) it fell 65% alongside stocks and bonds. It is an ultra-high-beta risk asset whose regime fingerprint mimics leveraged Nasdaq, not bullion.
2. **No cell admission.** The core matrix's evidence bar (two independent eras) is unmeetable for an asset with one macro cycle of history and n=9 stagflation months; and as G-cell octane it's a different asset (violating the "same asset, levered" rule) competing against TQQQ's validated +61%/yr with worse drawdowns. GDX — 40 years of history and a coherent mechanism — was just rejected on a weaker version of this evidence gap; consistency requires the same answer here.
3. **Legitimate shape if the user wants exposure**: a satellite belief-bet outside the rotation (the biotech precedent) — fixed small allocation (≤5%), spot-ETF wrapper at IBKR, rebalanced with contributions, never counted in tier targets, explicitly labeled unvalidated. Its one-era regime profile suggests if it ever were gated, it would be gated like a risk asset (on in G/D-rebound, off in S) — the opposite of the popular framing.

## Crypto satellite study — FILED, not deployed (2026-08-21)

Per user: study it, file it away. One-era (2014-09..2026-08, all of BTC's institutional life), 5% satellite added to tier baselines, monthly rebalanced:

| Variant | MOD | VAGG |
|---|---|---|
| baseline | +15.4%/2.39/−8% | +32.2%/1.26/−40% |
| +5% BTC fixed | +19.5%/3.03/−13% | +36.2%/1.52/−40% |
| **+5% BTC, 10m-trend-gated** | **+19.6%/3.22/−8%** | **+36.4%/1.52/−37%** |
| +5% BTC, G/D-regime-gated | +17.8%/2.80/−10% | +34.4%/1.42/−37% |

The trend-gated shape dominates: ~+4pp CAGR at ZERO drawdown cost (the 10-month SMA gate sat out the −74% BTC winters). Filed because the entire result rides one asset-era of +56%/yr BTC — no second sample exists or can exist, the same bar that excluded it from the matrix. If ever revisited: trend-gated, ≤5%, spot ETF, outside tier targets.

## Leverage timing study — REJECTED (2026-08-21)

User idea: time the octane by regime lifecycle (entering vs exiting, month-of-regime). Pre-registered gate: the age pattern must appear in both eras. Age-conditional MOD monthly returns — modern: m1 +1.01% / m2 +1.86% / m3-4 +1.56% / m5-8 +1.19% / m9+ +0.54%; pre-2007: +0.93 / +0.65 / +1.59 / +1.05 / +0.29. Stable both eras: months 3-4 are the sweet spot, month 9+ is the weakest. Era-flipping: months 1-2.

Portfolio variants (tier-ladder as the leverage dial, modern engine): RAMP1 (one notch down in regime month 1) looked seductive at octane tiers — AGG Sortino 1.22→1.36, VAGG 1.12→1.22, nearly free — but its mechanism is VOLATILITY at transitions, and that channel EXACTLY INVERTS across eras: modern month-1 median vol 15.6% vs 11.6% for old regimes; pre-2007 month-1 12.4% vs 15.6% for old regimes. The 2007-2026 sample's crashes happened to begin at regime flips; 1987-2006's turbulence lived in aged regimes. Classic sample artifact — rejected. TAPER9 (notch down from month 9): the one two-era-stable signal, but portfolio impact is sub-noise (−0.1..−0.6pp CAGR for +0.02..+0.06 Sortino). BOOST36 (notch up months 3-6): +4pp CAGR with worse Sortino and DD through the tier's risk envelope — that is not timing alpha, it is just holding a higher average ladder position, which already exists as "pick a higher tier."

**Conclusion: the leverage dial is the tier choice itself; timing it by regime age adds nothing robust in two eras.** Want more return → sit higher on the ladder and accept its drawdown; the ladder was built for exactly that.

## Dynamic-tier study: which risk basket per regime — REJECTED, with a design validation as the prize (2026-08-21)

User idea: choose the risk tier per regime — minimize risk where it makes sense, maximize where it does. Pre-registered rule: octane admissible in a quadrant only where the tier ladder is monotone in BOTH eras. Required building the first full pre-2007 leveraged tier proxies (2x/3x NDX, 3x VUSTX, 3x FSENX; price-index and no-tilt limitations disclosed, uniform across tiers).

**The ladder table (in-regime annualized, CONS→MOD→AGG→VAGG):**

| | Modern | monotone | Pre-2007 | monotone |
|---|---|---|---|---|
| G | +8.9 → +17.5 → +42.6 → +61.4% | YES | +13.3 → +21.1 → +44.3 → +57.7% | YES |
| R | +9.8 → +13.1 → +14.2 → +20.3% | YES | +8.1 → +9.4 → +11.8 → +16.3% | YES |
| S | +4.8 → +7.7 → +9.5 → +10.3% | YES | +8.5 → +10.3 → +11.8 → +13.0% | YES |
| D | +14.2 → +22.5 → +26.9 → +37.1% | YES | +12.5 → +17.4 → +12.8 → +11.6% | **no** |

**Mapping results: every dynamic mapping is dominated by fixed VAGG in BOTH eras** (e.g., octane-except-S: 33.5 vs 33.8 modern, 26.5 vs 26.9 pre-2007; octane-G-only: worse CAGR AND worse drawdown −56 vs −49). Mechanism: **the cells already do the risk timing.** VAGG's S-cell is 85% cash/duration and its D-cell is bonds+gold — the de-risking the mapping tries to add is already inside the tier. Dropping to MOD in defensive regimes only dilutes octane that was monotonically paying (7 of 8 era×quadrant cells). The maximize/minimize logic IS the matrix; the risk dial is the tier, the timing is the rotation. Zero-turnover-cost was real but there is nothing to buy with it.

**Byproducts, both valuable:**
1. **Strongest out-of-sample design validation to date**: the full tier ladder, built on modern data, is monotone in 7 of 8 era×quadrant cells on 1987-2006 proxies it never saw.
2. **Watch item — levered duration is financing-sensitive**: the one non-monotone cell (pre-2007 D: VAGG +11.6 < MOD +17.4) traces to 3x bonds paying 2×(rf+1%) financing when short rates were 5-9%; TMF's modern D-cell success partly rides the low-rate era. Pre-registered future candidate (NOT fitted now): condition the TMF slice on the short rate level. Revisit if the forward era keeps short rates elevated.
3. Calendar-month seasonality gate: correlation of the 12 monthly seasonal means across eras = +0.18 — no stable seasonal structure; axis closed.
4. First full pre-2007 tier stats (Nasdaq-proxy G-cells): CONS n/a computed, MOD +13.8%/1.40/−24%, AGG +21.2%/0.92/−46%, VAGG +26.9%/0.76/−66%. (Earlier +11.7% MOD replication used VFINX for the G-cell; NDX is the design-faithful proxy — difference disclosed.)

## Short-rate-conditional TMF test — carry rule rejected; TMF's true role quantified (2026-08-21)

Follow-up to the dynamic-tier study's watch item, run at user request. Pre-registered rule (mechanism-derived, no fitted threshold): hold the 3x duration slice only when the 30y yield exceeds the 3m bill + 1% (leverage the bond only when its carry pays the financing); else same weight unlevered.

**1. Carry-conditioning: REJECTED — the signal doesn't discriminate.** The curve is steep in nearly every D-month in BOTH eras (21/22 pre-2007, 22/30 modern) because deflation regimes coincide with Fed cutting cycles. The rule barely changes holdings and the deltas are noise (AGG modern 24.1→23.9, pre-2007 21.2→21.2). The pre-2007 damage was done by the LEVEL of financing (avg 3m bill 4.5% → ~11%/yr drag on a 3x position), which the spread rule cannot see.

**2. Level-conditioning: not adoptable on discipline.** Modern D-months averaged rf 1.5%, pre-2007 D-months 4.5% — any rf threshold splits the two ERAS, not months within an era. Choosing one is curve-fitting with n≈2 observations. Left to forward monitoring instead.

**3. The real finding — sleeve vs cell decomposition.** Standalone levered duration is weak in BOTH eras inside D-months: modern 3x TLT +2.2%/yr vs unlevered +7.0% (63% vol — daily-reset vol drag dominates even at ZIRP); pre-2007 +4.5% vs +6.4%. Yet the always-TMF vs never-TMF cell test shows the CELL is slightly better with it: modern AGG +0.2pp/VAGG +0.4pp CAGR with equal-or-better Sortino; pre-2007 a wash. TMF's value is not the sleeve's return — it is daily-rebalanced convexity against the gold/equity slices and crash-month spikes. **Verdict: keep TMF unconditional** (same asymmetric shape as the oil short, smaller: helps modern, harmless pre-2007), with the newly quantified comfort that dropping it entirely would cost only ~0.2-0.4pp — a cheap exit if the forward ledger ever shows the high-rate era turning the cell contribution negative.

## Factor & style screen — academically real, not investably adoptable (2026-08-21)

User request: screen factor/style exposures (momentum, value, quality, low-vol) through the framework. Data solution: Ken French long-only decile portfolios (monthly, one consistent source spanning BOTH eras — factor ETFs only start 2005-2013 and mostly miss 2008), with real-ETF implementability checks and an investable impact test for the survivor.

**Academic screen (top-decile, in-regime, both eras) — three candidates cleared the two-era bar vs their incumbents:**
- **Value in R**: +12.3% vs market +6.3% modern; +11.6% vs +8.5% pre-2007 (value = energy/financials/cyclicals — the reflation trade)
- **Momentum in G**: +25.2% vs QQQ +23.3% modern; +37.5% vs NDX +27.0% pre-2007
- **Quality in D**: +41.3% vs market +33.8% modern; +22.6% vs +10.9% pre-2007
- Confirmation: **high-variance junk is absolute-negative in S in both eras** (−17.7%/−18.7%) — independent support for the S-cell short thesis (not implementable as a short: no borrow/inverse vehicle).

**Implementability checks (real ETFs, in-regime) killed two of three:**
- Momentum: PDP +16.7% vs QQQ +23.3% in G-months (2007+); MTUM +20.5% vs +21.8% (2013+). The academic decile's monthly top-10% turnover cannot exist inside an ETF. Dead — and consistent with the earlier G-cell momentum-selection rejection.
- Quality: SPHQ +27.9% vs SPY +32.2% in D-months. Dead.
- Value: VTV +9.1% / IWD +7.9% vs SPY +7.0% in R-months — survives the modern wrapper (diluted from the academic +6pp to ~+1-2pp).

**Impact test on the survivor** (R-cell equity slice SPY→value; VTV modern, Vanguard Windsor VWNDX as pre-2007 investable proxy): modern improves (MOD +15.3→15.6%/1.73→1.77; CONS +9.7→9.9%) but **pre-2007 degrades (+11.8→11.3%/1.38→1.35)** — the academic pre-2007 value premium does not survive its own investable wrapper either. Fails the bar. **REJECTED; no matrix change.**

**Lesson recorded**: regime-conditional factor premia are academically real in both eras, but every investable wrapper tested surrenders the edge — high-turnover premia (momentum) can't be packaged, and diluted large-cap versions (value, quality) shrink below adoption thresholds. The factor axis is closed unless a materially better vehicle appears.

## Thematic-basket screen — axis closed (2026-08-21)

User question: real estate ETFs (already screened — IYR/FRESX sat in both sub-sector screens; mediocre in every cell both eras, never beats an incumbent, fails as a short) and thematic baskets (never screened — done now, 13 themes with the longest available histories, modern era, vs QQQ/SPY incumbents).

Results (in-regime annualized, full-period CAGR): the themes split into two families, both non-candidates.
1. **Diluted Nasdaq beta** (FDN internet, IGV software, SKYY cloud, HACK cyber, ARKK): some beat QQQ inside G or D months (FDN G +27% vs +23%; ARKK D +135%), but every one loses to QQQ over the full period (FDN +13.2%/yr vs QQQ ~16%; ARKK +13.6% from 2014 vs QQQ ~18% same window) — the in-regime edge is just higher beta, and the regime mix taxes it back.
2. **Narrative boom-busts** (TAN solar −7.1%/yr SINCE 2008, PBW clean energy −4.0%/yr over 21 years, ICLN −3.7%, URA −3.3%, KWEB +1.9%, JETS +2.2%, LIT +6.4%): negative-to-feeble two-decade CAGRs with −20-40%/yr stagflation legs. Live confirmation of the launch-at-attention-peak adverse selection documented in the ETF literature.

Structural point: no thematic fund has pre-2007 history, so matrix admission is impossible under the two-sample rule regardless (the crypto precedent). Nothing here even earns satellite-file status — unlike BTC, no theme shows an edge its diversified parent index doesn't already deliver cheaper. Axis closed.

## The final-frontier sweep: all eight untested ideas, one pass (2026-08-21)

User directive: test everything left on the TESTS.md untested list. Pre-registered, two-era where data exists (VWEHX daily to 1980, DXY to 1976 made most of them properly testable). Result: **eight ideas, zero adoptions — and one existing cell strengthened.**

1. **HY credit as a sleeve — REJECTED.** Beats no incumbent in both eras: modern D it beats TLT (+16% vs +7%) but pre-2007 D it loses (+3.4% vs +6.2%); everywhere else it trails equity or cash.
2. **HY credit as an early-warning signal — REJECTED.** "Equity trend up but credit trend down" predicts weaker months modern (+0.93 vs +0.76%/mo) but STRONGER months pre-2007 (+0.80 vs +1.38) — the direction itself flips eras.
3. **Dollar in stagflation — REJECTED.** Modern +8.0%/yr in S-months, pre-2007 **−7.8%/yr**. The UUP screen hit was the 2022 dollar surge wearing a regime costume. Textbook two-sample kill.
4. **International/EM sleeves — REJECTED.** Never beat the Nasdaq G-incumbent in either era; EM does −35%/yr in modern S. Confirms the G-cell momentum-select rejection from the other direction.
5. **TIPS — CLOSED on modern evidence alone** (+5.0% in R vs gold's +12.9%; worse than cash in S); the missing pre-2007 leg never becomes binding.
6. **Gold trend-gate in D — REJECTED, and the rejection is a gift.** In BOTH eras, D-months where gold sat BELOW its 10m SMA were gold's BEST months (+3.40%/mo modern, +6.34%/mo pre-2007, vs +1.37/−0.23 above-SMA): those are the crash-panic months where gold V-bottoms on flight-to-safety. A trend gate would have removed exactly the months the 30% slice exists for. Unconditional D-gold is now validated the same way unconditional D-duration was — by the failure of its own conditioning.
7. **Regime-transition conditioning — CLOSED.** No (predecessor→successor) pair shows a stable actionable deviation in both eras (R→G +1.7/+1.3%/mo, R→S +1.4/+1.8 — all near base rates).
8. **Commodity trend basket — REJECTED.** Modern 13-commodity trend (long above own 10m SMA, EW) beats DBC buy-and-hold (+4.0% vs +2.2%/yr, DD −40 vs −75) but earns it all in R (+10.1%/yr) where the matrix already owns commodities, LOSES −13.7%/yr in S (our ex-ante S-months are choppy inflections, not CTA-friendly trends), and the pre-2007 GSCI-trend leg shows no edge over buy-and-hold (+4.3 vs +5.1). Structural note: trend-gating the R-cell's DBC is a no-op — R classification already requires DBC above its SMA. No seat. (Yahoo roll-gap contamination disclosed but not binding: the S-month failure is too large to be a data artifact.)

## Decumulation spec (pre-registered, dormant until ~age 60)

The glide path ends at CONS at 65; the withdrawal phase needs rules, specced now so they get tested with decades of forward ledger behind them: (1) hold 2 years of spending in the cash/duration sleeve; (2) monthly withdrawals draw from cash; (3) refill cash from risk sleeves only in G/R-classified months — never sell equity into S/D; (4) skip inflation adjustments after negative portfolio years; (5) initial rate 3.5-4% (CONS's −10% maxDD and +13.8% 2008 make the classic sequence-risk failure mode structurally mild, but this is asserted, not yet tested). Test before first withdrawal, not before.

## Liquidity-plumbing signals: CCC stress, BOJ assets, the yen — all rejected (2026-08-21)

User proposed three macro-liquidity early-warning signals. Pre-registered: signal at month-end t predicts month t+1; 10m-SMA-style flags; each series' history split into halves as independent sub-samples. Data notes: FRED now caps anonymous downloads at 3 years, killing direct ICE BofA CCC OAS history — proxied with FAGIX (Fidelity Capital & Income, 1980, the junkiest large HY fund) vs long Treasuries, disclosed as returns-based; BOJ assets (JPNASSETS, 1998+) and Fed assets (WALCL, 2002+) fetched fine; USDJPY from 1996.

1. **Deep-junk credit stress ("CCC spreads rising") — REJECTED.** In months where the equity trend is up (G/R) but junk credit is trending down vs Treasuries: pre-2007 those months were BETTER (+1.61%/mo vs +0.77% calm); modern, trivially worse (−0.11% spread). This is the THIRD credit-canary design to fail (VWEHX broad HY signal, now FAGIX deep junk) — at monthly horizon, whatever credit knows is already in the equity price.
2. **BOJ assets → Nasdaq — REJECTED.** 1998-2011: correlation −0.20 with monotonically DECLINING quintiles (fastest BOJ expansion → −1.6%/mo next-month Nasdaq) — the balance sheet grows reactively, during stress. 2012-2026: +0.02, nothing. Even the contemporaneous 12m-vs-12m narrative correlation is −0.03. The famous overlay chart does not survive arithmetic.
3. **Yen strength / carry-unwind warning — REJECTED, direction backwards.** After yen-strong months (USDJPY < 10m SMA), equities did BETTER in both halves (+0.77 vs +0.03%/mo 1997-2010; +1.64 vs +0.88 2011-2026) — yen strength accompanies Fed-easing/weak-dollar regimes, which are risk-friendly. The sharper "yen surge" (top-decile 3m appreciation) flips sign across halves (−0.04 then +2.39%/mo — post-surge months in the modern half were capitulation rebounds, e.g., Aug 2024). Descriptive footnote: USDJPY does track the Fed/BOJ asset ratio (level corr −0.51) — the FX-liquidity link is real; it just carries no equity-timing information at monthly horizon.

Structural reading, three-for-three: liquidity plumbing is upstream of prices in narrative but downstream in tradability — by month-end, the SPY/DBC trend has already priced what the plumbing "warned" about, and intra-month carry spikes are unreachable at monthly cadence (and intra-month mechanisms are a proven graveyard under T+1). The classifier needs no fifth input.

## CCC blowouts and min-vol: the fact confirmed, the trade absent (2026-08-21)

User claim: when CCC spreads blow out, USMV outperforms, and vice versa. **Confirmed as stated — contemporaneously**: same-month correlation of CCC OAS widening with USMV-minus-SPY is **+0.60** on the real ICE BofA series (2023-2026) and +0.51 on the deep-junk proxy (2011-2026); the mirror holds for high-beta (SPHB-minus-SPY corr −0.54). Spreads and defensive rotation are two prints of the same risk-off shock.

**The tradable version fails.** Knowing the stress state at month-end t does not predict month t+1's low-vol relative return: 1981-2006 spread −0.02%/mo (nothing), 2007-2026 +0.33% (mild), USMV ETF 2011-2026 −0.23% (wrong direction) — era-inconsistent and tiny. The contemporaneous correlation is a hedging identity, not a signal: by the time the blowout is observable, the min-vol outperformance has already been paid. Trading it requires predicting NEXT month's spread change, which is just predicting risk-off itself — the thing the whole signal family (entries 41-43) keeps failing to do.

One consistent secondary fact, no action required: the HIGH-vol decile underperforms in the stress state in both eras (−0.26/−0.35%/mo spreads) — "don't hold junk stocks when credit is stressed" is real, but the matrix never holds the high-vol decile in any cell, so the advice is already structurally followed. Framework reading: the regime cells ARE the min-vol rotation, executed slowly and honestly — when stress regimes classify, the book already holds the defensive assets that the CCC-USMV correlation points at.

## VIX term structure as a signal — rejected (2026-08-21)

Data: CBOE official VIX (1990+) and VIX3M (2009-09+ — no 2008 in the ratio sample, disclosed; Yahoo's ^VIX3M is broken, one row). Ratio = VIX/VIX3M at month-end; inverted (>1) = backwardation. Halves 2009-2017 / 2018-2026.

1. **As a danger signal: backwards.** Month-end backwardation precedes BETTER months in both halves (+1.76 vs +1.13%/mo; +2.21 vs +1.16). At monthly frequency, inversion is a capitulation marker, not a warning — the panic has already printed and the next month mean-reverts.
2. **As a de-risk overlay in trend-up months: never fires.** Only 5 and 3 G/R-classified month-ends with inversion per half — backwardation and classifier trend-breaks are nearly simultaneous events; there is nothing left to act on that the regime switch doesn't already do.
3. **The one consistent pattern runs the OTHER way**: steepest-contango (calmest quartile) month-ends precede WEAKER months in both halves (+0.54 vs +1.37; +0.60 vs +1.49) — complacency, not panic, is the mild warning. But forward returns remain positive (de-risking on it costs absolute return), the sample is one era by construction (VIX3M's 2009 birth), and it cannot ever clear the two-sample bar. Noted, not tradable.
4. VIX level vs own trend (1990+, the long-history supplement): era-flip (no difference 1991-2008, high-VIX-better 2009-2026). Nothing.

Fifth member of the signal-family graveyard (credit ×3, liquidity ×3, now vol structure): every popular early-warning indicator is either simultaneous with the price trend, backwards, or era-unstable at monthly horizon.

## Valuation-at-bottoms and financials-as-leader — both rejected (2026-08-21)

**Valuation (Shiller CAPE, 1881+, tested 1987-2026): REJECTED — cheap gets cheaper.** Within defensive-classified (S/D) months, CAPE state vs its own trailing 10-year distribution shows no usable pattern: pre-2007 non-monotone (rich +1.37%/mo, mild-cheap −1.73%, extreme n=2); modern INVERTED — "extremely cheap" months averaged **−0.28%/mo** (n=24), because CAPE sat below its 10-year 25th percentile through the entire 2008-09 collapse while prices kept falling. Valuation identifies WHERE bottoms happen eventually, not WHEN — the one thing a bottom signal must do. Bonus finding: even the famous long-horizon version fails era-consistency in our samples — cheap beat rich pre-2007 (+13.7% vs +11.6% forward-12m) but rich beat cheap modern (+13.9% vs +10.3%); CAPE's 21st-century breakdown, reproduced in-house.

**Financials as the economy's leading indicator: REJECTED — exact era inversion.** Relative-strength flag (XLF/SPY modern, FIDSX/VFINX pre-2007, ratio vs 10m SMA): in defensive months, pre-2007 fin-WEAK preceded rebounds (+3.07%/mo vs −0.59% when healthy — capitulation again); modern the story runs the other way (fin-healthy +2.98% vs +0.87%) — spreads of −3.66% and +2.12%, a perfect flip. In trend-up months: −0.06% vs +0.61%, also flipped. Monthly lead-lag correlations are ~zero in both directions in both eras (if anything the MARKET slightly leads financials, +0.09/+0.12). "Financials lead" is narrative, not data, at monthly horizon.

Signal graveyard count: nine (credit ×3, liquidity ×3, vol structure, valuation, financials). Recurring anatomy of bottoms across all of them: bottoms are marked by everything looking broken — junk credit collapsing, VIX inverted, financials dying, valuations "cheap and getting cheaper" — which is precisely why waiting for any health indicator misses the turn, and why the price trend, late as it is, keeps beating every attempt to front-run it.

## Bottom-signal round two: turn signals, not state signals (2026-08-21)

User prompt: bottoms move fast, tops are slow — find bottom signals. The nine dead signals were mostly STATES; this round tested five TURN/washout designs, month-end signal → next-month equity, WITHIN defensive-classified (S/D) months, both eras:

| Signal | Pre-2007 (off vs ON) | Modern (off vs ON) | Verdict |
|---|---|---|---|
| **1a. Breadth washout** (<25% of 17-18 sectors above own 10m SMA) | +0.31 vs **+1.69**%/mo | +0.87 vs **+1.48**%/mo | **PASSES — first two-era-consistent bottom signal** |
| 1b. Breadth thrust (+30pp in 2mo) | n=4 | n=4 | never fires while still classified S/D — the regime flips first |
| 2. Vol crest passed (realized vol falling) | +1.80 vs +0.07 | +0.09 vs **+2.95** | exact era inversion — dead (the leverage-timing autopsy's vol flip, again) |
| 3. Crash last month (<−5%) | +1.04 vs +0.53 | +1.48 vs +0.95 | crashes beget crashes mildly — no mean-reversion edge |
| 4. Fed easing (3m bill < 6mo ago) | +1.59 vs +0.64 | +3.14 vs **+0.16** | consistent NEGATIVE both eras — cuts confirm recessions, they don't rescue them; the book is already defensive, so no action, but recorded as a real (inverse) finding |
| 5. Credit turn (junk rally inside S/D) | +1.27 vs +0.07 | +1.49 vs +0.82 | junk rallies inside defensive regimes are bear-market rallies — consistent mild negative |

**Impact test on the survivor — washout-conditional D-cell rebound slice** (+10pp to the cell's equity asset from TLT when breadth <25% at month-end; signal is month-end-observed, no intra-month machinery, no T+1 exposure):

| | CONS | MOD | AGG | VAGG | MOD pre-2007 |
|---|---|---|---|---|---|
| baseline v6 | +9.7/1.60/−10 | +15.3/1.73/−14 | +24.1/1.22/−34 | +33.8/1.12/−49 | +11.8/1.38/−24 |
| washout-tilt | +10.0/1.63/−11 | **+15.6/1.75/−14** | **+24.6/1.25/−33** | **+34.4/1.13/−49** | **+11.9/1.39/−24** |

Improves every tier modern AND improves pre-2007 — the same asymmetric-or-better profile as the adopted R-tilt and energy short, at comparable magnitude (+0.3-0.6pp). Mechanism-coherent: it enlarges an already-validated slice (the D rebound equity) conditionally, exactly in the months where forward returns have historically been strongest in both eras, addressing the known rebound-lag weakness WITHIN the monthly cadence. Note: CONS's drawdown deepens slightly (−10→−11%); recommendation is to adopt for MOD/AGG/VAGG and leave CONS untouched (mandate purity, same precedent as the shorts).

### Adopted: matrix v7 — washout-conditional D rebound slice (2026-08-21)

User approved for MOD/AGG/VAGG; CONS untouched. Wired: `WASHOUT_REBOUND` map + `WASHOUT_SHIFT` (10pp from TLT to the tier's rebound asset — SPY/QQQ/QLD; VAGG's shift caps at its 5pp TLT weight), `breadth_washout` parameter in `resolve_allocation` (fail-closed: None/False → standard cell), breadth signal in the paper logger (18 sector ETFs, share above 10m SMA of completed months, ≥12 names required else unknown→fail-closed, threshold <25%), breadth + washout recorded in the ledger's signals JSON. 65 tests pass. Official v7 numbers (workbook refreshed): CONS +9.7%/1.60/−10.2 (unchanged), MOD +15.6%/1.75/−14.3, AGG +24.6%/1.25/−33.4, VAGG +34.4%/1.13/−48.9. Honest trade visible in the year rows: MOD's 2008 falls +20.7→+15.4% (the tilt buys equity into late-2008 washouts) while the full period gains — buying washouts costs something inside the crash year and earns more across the cycle. Why the gain is only +0.3-0.6pp despite a 0.6-1.4pp/mo signal edge: the tilt moves 10pp of weight, in D-months only (~13% of months), in the washed-out subset (~20-25 fired months in 19 years) — per-decision edge large, exposure small, by design. Live from the September 2026 ledger run.

## Leveraged-ETF decay: validated, and one restatement (2026-08-21)

User question: did we factor in decay? Yes — structurally: the sim is daily-reset (N× daily return − (N−1)×(rf+100bp)/252 − ER, compounded daily), so volatility decay emerges from the compounding path rather than being a bolt-on haircut. It is visible in our own results (3x TLT +2.2%/yr in D-months vs +7.0% unlevered — the decay, measured). Sim-vs-real validation over each product's live history:

| Product | daily corr | sim CAGR − real CAGR |
|---|---|---|
| QLD | 0.996 | −0.5%/yr (sim conservative) |
| TQQQ | 0.999 | −1.3%/yr (conservative) |
| TMF | 0.997 | −0.7%/yr (conservative) |
| SCO | 0.974 | −0.3%/yr |
| ERY (2x, post-2020 product) | 0.999 | −2.6%/yr (conservative) |
| ERX sim-as-3x | 0.997/0.999 | matches pre-2020 real; **+7.4%/yr optimistic vs post-2020 real** |
| ERX sim-as-2x | 0.999 | matches post-2020 real (−0.2%/yr) |

**Restatement**: Direxion cut ERX (and ERY) from 3x to 2x in March 2020. The v2 design doc said ERX(2x) but every engine simulated 3x. The tradable product today is 2x, so the engine now models 2x — only VAGG holds ERX (R-cell), so only VAGG restates: **CAGR 34.4→32.9%, Sortino 1.13→1.12, maxDD −48.9→−46.9% (shallower), 2026 YTD 49.9→36.7%** (this year's energy run at true 2x). CONS/MOD/AGG unchanged. Workbook refreshed. Note the forward paper ledger was never affected — it marks to market with REAL ERX prices; only backtest statistics carried the 3x assumption.

## Leverage audit part two: realized betas today, and the SCO restatement (2026-08-21)

User question: are the other levered ETFs still the same leverage today? Measured by realized daily beta vs underlying, trailing 12m/3m and yearly through each product's life:

| Product | today | history | verdict |
|---|---|---|---|
| QLD | 1.99 | 2.0 every period since 2007 | unchanged |
| TQQQ | 2.97 | 3.0 throughout | unchanged |
| TMF | 2.92 | ~3.0 throughout | unchanged |
| ERX / ERY | +2.00 / −2.00 | 3x until Mar 2020, 2x since | matches yesterday's restatement |
| **SCO** | **−1.3 vs USO** | −2.0 until 2019, drifting since | **flagged — see below** |

**SCO's drift is basis, not leverage**: SCO still runs 2x inverse of ITS index, but USO restructured in 2020 (multi-month futures basket) and the two have diverged — realized beta vs USO is now ~−1.3. The backtest modeled the D-cell short as a clean −2x of USO; the real vehicle demonstrably was not, most dramatically in April 2020 (negative oil): synthetic +72% that month, real SCO **−7%**.

**Restatement — hybrid convention adopted**: the stats engine now uses REAL product returns wherever the product existed (SCO from Nov 2008) and synthetic-of-today's-spec before inception. ERY stays synthetic-2x throughout (its pre-2020 3x incarnation no longer exists; post-2020 real tracks our synthetic within −2.6%/yr, conservative). Official v7 numbers restated: MOD +15.3%/1.72/−14.3, AGG +24.2%/1.23/−33.4, VAGG +32.4%/1.11/−47.0 (CONS unchanged; cumulative cost of the two audit restatements at VAGG: 34.4→32.4%). Workbook refreshed.

**Deployment note**: at today's −1.3 realized beta, a 5% SCO position delivers ≈ −6.5% oil exposure per 10% sleeve rather than the modeled −10% — the live short runs undersized, which the hybrid backtest now prices. Cheapest-to-hold inverse oil vehicle it remains; the sleeve is small and the regime self-limiting either way. The audit lesson, recorded: products drift under you — realized-beta checks belong in the periodic review alongside the ledger.

## "Quadrant balances" reconstructed — the top-signature confirmed, no new action (2026-08-21)

User described a breadth phase-clock from a prior job: four phases of a breadth oscillator (1 falling-decelerating/pre-bottom, 2 rising-accelerating, 3 rising-decelerating/late-cycle, 4 falling-accelerating/crash) plus a time-in-phase counter, S&P-focused. Reconstructed as a phase-plane of the two-era sector-breadth series (direction × acceleration of the 3m-smoothed share-above-trend), month-end sampled, tested both eras.

**What replicates across both eras:**
- **Q3 (rising but decelerating) is the weakest forward phase in BOTH eras** (+0.51/+0.40%/mo vs +0.8-1.7% elsewhere) — the "slow top" signature is real: breadth deceleration while still rising is the most era-stable warning any signal has shown in this whole program. But its forward months remain POSITIVE, so acting on it costs absolute return — the same untradable shape as steep-contango complacency (entry 45).
- **Falling-breadth phases (Q4/Q1) precede strong months in both eras** (+1.1-1.7%/mo) — the capitulation family again, already harvested by the v7 washout tilt.

**What does not replicate:** WHICH falling phase is best inside defensive regimes flips eras (Q1 +1.95% pre-2007 / −0.65% modern; Q2 +0.12% / +1.87%) — the phase adds no stable refinement to the washout level signal, and phase-gating the v7 tilt (e.g., blocking Q4) would have HURT both eras (Q4-in-S/D forward months are good: +1.36/+1.71%). The age counter compresses at monthly frequency (ages rarely exceed 3-4; the original tool was likely weekly, where >10 readings mean something) — its cells are too small to judge, and a weekly-actioned version would land in the proven intra-month/T+1 graveyard. **Verdict: the tool's qualitative story (slow tops via breadth deceleration, fast bottoms via washout) is two-era TRUE; its actionable monthly content is already inside the classifier + v7 washout tilt. No change.**

### Quadrant balances, the member-level "main version" (2026-08-21)

User clarified the real tool: each stock classified into its own phase, the BALANCE = population counts per quadrant, computed at daily/weekly/monthly/yearly frequencies (nested cycles). Rebuilt member-level on the 17-18 sector series (granularity disclosed: sectors, not 500 stocks), phases per member (3m-smoothed direction × acceleration), month-end sampled; weekly-fed variant (13w smoothing, sampled monthly) for the modern era; yearly skipped honestly (3-4 supercycles in 40y = narrative, not statistics).

**Findings:**
1. **High share-in-Q4 (members in crash phase) → better next months in BOTH eras**, and it is the best bottom discriminator yet measured inside S/D months: high-%Q4 +1.42 vs +0.13%/mo pre-2007, +1.89 vs +0.74 modern; the weekly-fed version is stronger still (+2.06 vs +0.48). The member distribution carries real information.
2. **Incremental over the adopted washout flag**: yes at the month level — "Q4-only" S/D months (balance fires, level-flag doesn't) ran +1.24/+1.72%/mo in the two eras. **No at the portfolio level**: widening the v7 tilt to (washout OR high-%Q4) changes tier results by ≈0.0-0.1pp — the extra months land mostly in S (where the equity tilt doesn't apply, by prior validated design) or already coincide with washout in D. The v7 tilt is already harvesting what is actionable.
3. Verdict: **no v8; the member-balance version enriches the science and validates the user's tool a second time** (its %Q4 spike = the capitulation the system buys; its Q3 signature = the slow-top warning confirmed earlier). Revisit trigger (pre-registered): if forward-ledger defensive months ever show the level-washout misfiring where the weekly-fed balance disagreed, rerun this comparison on live data.

Implementation status for clarity: everything in this section is research scratchpad only — the LIVE system's breadth machinery remains exactly v7's level-washout tilt, nothing more.

### Quadrant balances on the actual S&P 500 (2026-08-21)

User: "test it on the S&P 500, trust me." Done: 499 of the current 503 members (survivorship-disclosed — today's roster, histories to 1985; 202 members reporting at start), member phases monthly, ≥150 reporters required.

**The user was right — the real-index version is the sharpest bottom discriminator ever measured here.** Within defensive months: high-%Q4 → next-month S&P **+1.43% vs −0.02%/mo** pre-2007 (spread +1.45pp) and **+2.23% vs +0.32%** modern (+1.91pp), era-consistent, top-quartile %Q4 strong in both eras overall (+1.43/+1.47 vs +0.89/+0.78).

**And the book still doesn't change.** In the 30 modern D-month stamps (the only place the tilt acts): the S&P signal and the sector washout coincide 16 times, washout-only 5, S&P-only 2, neither 7. Portfolio impact: swapping the tilt input to the S&P signal is slightly WORSE (−0.2pp everywhere — it misses 5 washout-flagged D-months); OR-ing them is IDENTICAL to v7 to the decimal. The S&P version's extra sharpness lives in S-months and non-defensive months where the tilt deliberately cannot act. Operationally it would also cost ~500 fetches/month vs 18. **Verdict: v7 unchanged; the S&P-500 member balance is canonized as the program's best bottom DIAGNOSTIC — a dashboard, not a lever — and the user's prior-job tool is now three-for-three on two-era validation of its qualitative claims.** Today's live balance for the record: Q2-dominant at 48% (Q1 14 / Q3 20 / Q4 18) — mid-cycle acceleration, agreeing with the Reflation classification.

**Adopted as an informational ledger line (2026-08-21, user request):** the monthly logger now fetches the current S&P 500 roster (datahub constituents CSV) + each member's monthly closes, computes the balance on completed months, and records it in the signals JSON as `sp500_balance` ({q1..q4, dominant, n}). Strictly informational — it feeds no resolution, and any fetch failure logs None without blocking the row (fail-soft, ≥150 members required). Adds ~2-3 minutes to the monthly run. From September 2026 the ledger carries the user's old dashboard beside the system's decisions, accruing a forward record of both.

## LEAPS as the leverage engine — rejected today, filed with an account-size trigger (2026-08-21)

User question: did we ever look at LEAPS/options? Options strategies exist as FILED items (IBS overlay, CL surge calls — both pending the IB Gateway execution layer). LEAPS-as-leverage (deep-ITM long calls replacing QLD/TQQQ) analyzed here against live quotes (QQQ spot 713, Sep-2027 chain):

| moneyness | mid | 1 contract | eff. leverage | embedded financing/yr | spread |
|---|---|---|---|---|---|
| 50% | $376 | **$37,600** | 1.9x | 4.7% (≈ rf+1%) | 1.0% |
| 70% | $246 | $24,600 | 2.9x | 6.1% | 1.3% |
| 80% | $188 | $18,800 | 3.8x | 7.3% | 1.7% |
| 90% | $135 | $13,500 | 5.3x | 8.9% | 2.5% |

**Four blockers, in order of severity:**
1. **Granularity**: every single contract costs more than the entire account (~$12k). No tier sizing, no rotation granularity, no diversified cell possible.
2. **Costs beat the ETFs only at low leverage**: 50%-moneyness financing (4.7%) merely MATCHES the modeled levered-ETF financing; pushing toward the ETFs' 2-3x costs 6-9%/yr embedded plus 1-2.5% bid-ask crossed at entry, at every annual roll, and at every regime rotation (3.2 switches/yr; median hold 2 months) vs ~1bp on QLD. The LEAPS advantages (no daily reset, LT tax at >1yr holds, defined loss) all require HOLDING — precisely what the rotation doesn't do.
3. **The convexity is redundant**: the extrinsic paid is the variance risk premium (persistently overpriced), buying a crash floor the classifier already manufactures by rotating to defensive cells.
4. **No validatable backtest exists**: free historical LEAPS data doesn't exist; the levered-ETF sims were validated at 0.997-0.999 daily correlation to real products, while a LEAPS sim would rest on modeled IV surfaces with nothing to check against — sub-house-standard evidence by construction.

**Filed with trigger**: revisit at ~$150k+ account, where 1-2 deep-ITM 50%-moneyness contracts (1.9x at rf+1%, defined max loss, possible LT treatment in G-regimes that persist >1yr) become a sizeable QLD-alternative for the G-cell. The options roadmap otherwise remains the FILED IBS overlay + CL calls behind IB Gateway.

## Six-idea batch: levered sectors, fast SMAs, metals, ags, dip-buying, cash (2026-08-21)

1. **Levered sector ETFs** — mostly settled: ERX is already in VAGG-R; leverage cannot rescue rejected exposures (a levered version of a failed sector is a bigger failure). The one open slot — 2x gold (UGL) in the AGG/VAGG D-cells — is evidence-equivalent to the REJECTED GDX swap (the pre-2007 proxy is a miners fund ≈ levered gold, so the two-era test is structurally incomplete in exactly the same way). Same call by the user's own precedent; not re-litigated.
2. **Faster entry SMAs (asymmetric: fast entry, 10m exit) — verdict REVISED after the user's structural challenge (see below).** Initial read: era flip (modern +2.2pp, pre-2007 −0.6pp at 5m entry) → reject. User's counter: post-2007 markets are structurally faster (indexing, systematic flows) — the eras shouldn't be weighted equally for a RE-ENTRY-SPEED parameter. The pre-registered discriminator (trend vs episode): the fast-entry edge by sub-period runs −0.2, −1.1, **+2.4, +1.0, +2.2, +3.3**%/yr — negative in both pre-2007 decades, positive in ALL FOUR modern 5-year windows including both modern GRIND bears (2007-11 contains the GFC: +2.4; 2022-26 contains the 2022 bear: +3.3). The two biggest disagreement-month wins were May 2009 and Nov 2022 — both grinds, not flash crashes. The structural-shift hypothesis has a data signature. Counterweights: the whole effect lives in 13 disagreement months in 40 years, and the parameter is the classifier itself — the highest-stakes object in the system. **Resolution: SHADOW CLASSIFIER wired into the ledger (2026-08-21)** — identical quadrant logic with a 5m-SMA entry leg (10m exit, inflation leg unchanged, monthly re-evaluation exactly as backtested), logged as `shadow_quadrant` in the signals JSON, informational only. The logger emits a loud warning on any live disagreement. **Pre-registered adoption trigger: the shadow is promoted only if it wins the majority of its first several LIVE re-entry disagreements with the primary** (historically ~1 disagreement per 3 years — a slow, honest trial the forward ledger adjudicates).
3. **Other metals — CLOSED on modern evidence.** Silver is high-beta gold with a −34%/yr S-leg (vs GLD −9%); copper −24% S; palladium −48% S; platinum weak everywhere. None beats GLD at the incumbent's job (crisis ballast + reflation participation); the missing pre-2007 legs never become binding.
4. **Agricultural commodities — CLOSED on modern evidence.** DBA +2%/yr in Reflation vs DBC's +11% — ags underperform the incumbent in the one regime commodities own; grains basket similar (+8%) with a −23% S-leg.
5. **Blue-chip dip-buying (≥35% below 12m high) — DATA-BLOCKED; reported number is an upper bound, not evidence.** On current S&P members the dip basket shows +2.21%/mo excess pre-2007 and +1.13%/mo modern — but survivorship bias MANUFACTURES precisely this result: today's roster contains only the companies whose crashes recovered (the AAPLs of 2008) and omits the Lehmans, Enrons, and Circuit Cities that defined the strategy's true risk. UNH/BA-style dip-buying cannot be honestly evaluated without delisting-inclusive data (CRSP-grade, paid). Filed as data-blocked; also outside the ETF mandate (single-name risk).
6. **Interest-bearing cash — already the adopted design** (SHY, +0.35%/yr over rolled bills; note: IBKR pays zero interest on idle cash below $10k, so the ETF form is mandatory at this account size). Refinement tested — regime-conditional bills (BIL in S): modern S favors BIL (+2.2 vs +1.6%) but pre-2007 S flips hard (2y duration +7.4% vs bills +2.8% — growth-scare stagflations had falling short rates). Era inversion; SHY stays everywhere.

## Overnight vs intraday decomposition (2026-08-21)

User request: decompose returns into overnight (prev close→open) and intraday (open→close) across the book's ETFs. Full histories, split-half checked:

| ETF | overnight/yr | intraday/yr | halves stable? |
|---|---|---|---|
| SPY (1993+) | **+10.1%** | +0.7% | yes (+11.1/+9.0) |
| QQQ (1999+) | **+13.9%** | −2.8% | yes (+14.6/+13.3) |
| IWM | +13.5% | −4.1% | yes (+13.5/+13.4) |
| XBI | **+23.2%** | −8.9% | yes-ish (+26.8/+19.6) |
| XLE | +12.9% | −3.4% | yes |
| GLD | +11.0% | 0.0% | yes (London/Asia hours) |
| **TLT** | **+0.4%** | **+3.1%** | direction holds | 

**Findings:** (1) The overnight anomaly is real and split-half stable in the majors — essentially ALL of equity ETFs' long-run return accrues while the US market is closed; intraday drift is zero-to-negative. XBI is the extreme case (+23% overnight vs −9% intraday — biotech news is announced off-hours, consistent with our 8-K event study). (2) **Bonds run the OPPOSITE way**: TLT accrues intraday. (3) As a STRATEGY it remains untradable, as the literature found: capturing overnight requires 252 round-trips/yr (~2.5-5% costs), 100% ST gains, and overnight-only funds have failed commercially. No matrix change.

**Adopted as a free execution habit (DEPLOYMENT.md)**: at monthly rotations, execute equity-ETF BUYS near the close and equity SELLS near the open; bond-ETF trades the reverse (buys near open, sells near close). Worth single-digit bps/yr at our turnover — adopted because it is free and directionally grounded in 30 years of stable data, sized honestly as bps.

## Daily overnight/intraday rotation — the toll-booth arithmetic (2026-08-21)

User: what about a strategy that rotates that often? Tested the full-capture version — QQQ held close→open (its accrual window), TLT held open→close (its window), every day, 2002-2026, ~1,000 trades/yr, auction-fill assumption (MOC/MOO orders receive the official open/close = the backtest's own prices, so the only per-trade costs are commissions/auction fees):

| variant | CAGR / Sortino / maxDD |
|---|---|
| GROSS (zero cost) | +15.1% / 1.17 / −45% (split-half stable: 15.9/14.4) |
| 0.5bp per side (best realistic case) | +9.5% / 0.73 / −45% |
| 1bp per side | +4.1% / 0.32 / −45% |
| 2bp per side | **−5.9% / ruin** |
| QQQ buy-and-hold, same window | **+15.9% / 0.96 / −53%** |

Three verdicts: (1) even GROSS, the combo does not beat QQQ buy-and-hold on level (+15.1 vs +15.9) — the anomaly's advantage is only risk-shaped (higher Sortino, shallower DD); (2) each 0.5bp of per-side cost consumes ~5.5pp/yr at this trade count — the strategy loses to B&H at the FIRST bp; (3) after tax it's +7.2%/yr (all ST, taxed annually) vs B&H compounding pre-tax with deferral. **REJECTED — and generalized: at ~1,000 trades/yr, ANY strategy needs a gross edge of ~5-11pp/yr per bp of round-trip cost just to stand still, before surrendering deferral. High-frequency rotation is structurally unavailable to a taxable retail account regardless of the signal's quality.** The system's monthly cadence is the sweet spot this arithmetic implies: few enough trades that costs round to zero, frequent enough to harvest regime change.

## The strategy-ETF shelf: can a fund do the rotating? (2026-08-21)

User idea: maybe packaged ETFs replicate parts of the system — hold the fund, let it rotate. Screened 18 strategy funds (managed futures DBMF/KMLM/CTA/WTMF, tactical TRTY/GAA/XLSR, vol-rotation PHDG, stacks/parity NTSX/RPAR/SWAN, covered calls JEPI/QYLD/XYLD, hedged/buffer HEQT/BUFR, static AOR/AOA) — each against our v7 MOD over the fund's OWN lifetime window.

**Headline: not one of the 18 beats MOD in its own window — on CAGR, Sortino, OR drawdown. Most don't beat plain SPY.** Best of shelf: XLSR +13.2%/0.82/−33%, NTSX +12.8%/0.87/−31%, JEPI +11.6%/1.38/−14% — vs MOD's same-window +19-23% / 1.7-2.6 / −10-14%. The longest-lived managed-futures ETF (WTMF, 2011) compounded at +1.3%/yr for fifteen years. The closest philosophical competitor — PHDG, a rules-based vol-triggered rotation fund running since 2012 — earned +5.6%/yr vs our +15.9% over the same window: its D-months are excellent (+27.9%/yr) but it pays for always-on hedging with +3.3%/yr Growth months; regime-SWITCHED defense beats always-hedged defense by roughly the difference. And the user's own example closed the loop: NightShares' overnight ETF (NSPY) launched 2022 and was LIQUIDATED within a year — the toll-booth arithmetic, adjudicated by the market.

**The one genuine find: managed futures delivered in the 2022 stagflation.** In S-classified months, KMLM +20.8%/yr and DBMF +14.1%/yr (n=9, essentially one episode) vs our S-cell's +7.7% — multi-asset trend (rates/FX/commodities, the thing our clean-data limitation blocked) doing what the literature promises, in the one regime where our cell is weakest. But: nine months, one era, and both funds bleed elsewhere (KMLM −2.5%/yr in G; DBMF −14%/yr in D-months) so holding them permanently costs more than their S-months earn. **FILED with a pre-registered forward trigger (the shadow-classifier pattern): if DBMF/KMLM outperform the S-cell allocation over the next ≥4 LIVE S-classified months in the forward ledger, test a 10-15% S-cell sleeve.** We would still be the ones rotating — the fund is a candidate INSTRUMENT for one cell, not a replacement for the system. **Watchlist wired into the ledger (2026-08-21, user request)**: every row's signals JSON now carries `managed_futures` — DBMF and KMLM's prior completed-month returns — so the trigger adjudicates itself from ledger rows alone (row T holds the regime in force; row T+1 holds what the funds earned during it). Informational, fail-soft, feeds no resolution.

Strategic conclusion, three lines: nothing on the shelf sells what the matrix does (tiered regime rotation with conditional cells and a short book); the wrapper-eats-edge law held for the fifth consecutive category; and the "just hold" convenience is priced at roughly half the return — 7-10pp/yr — which is the fee, in expectation, for not doing the 15 minutes a month.

## Findings

1. **The 33/33/33 TQQQ/GLD/TLT mix the user read about is real but mislabeled as balanced**: +19.7% CAGR and Sortino 1.13, but −51% max drawdown and beta ≈ 1.0. Its failure mode is precisely a regime event: **2022 (−41.9%)**, when inflation broke the bond leg at the same time the levered equity leg fell — the two "ballasts" and the engine all sank together. 2008 was −34%.
2. **The QLD (2x) version dominates it risk-adjusted**: Sortino 1.19 vs 1.13, −37% vs −51% DD, at +15.3% CAGR — a better default for the same idea.
3. **Static leveraged mixes vs the indices strategy**: the 33/33 mixes earn their return from *diversified always-on leverage*; the indices strategy earns it from *timing*. Their drawdown profiles are complementary (mixes die in inflation years like 2022 [−42%] which the trend strategy sidestepped [−5%]; the trend strategy bleeds in chop like 2015-16 which the mixes shrugged off). Combining them is the obvious next test.
4. **Regime portfolios post the best headline numbers** (AGG: +22.4%, Sortino 1.11, −32%, Sharpe 0.95) but carry the design bias flag; their honest validation is forward paper trading or a pre-2007 replication with different-era ETF proxies.
5. Every leveraged-ETF result relies on the daily-reset simulation assumptions; real TQQQ tracking since 2010 is close to this model, but pre-2010 numbers are model, not history.
