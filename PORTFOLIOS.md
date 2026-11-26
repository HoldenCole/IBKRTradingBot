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

## The pitched NDX top-10 momentum model — replicated, decomposed, declined (2026-08-21)

User shared a screenshot pitch: NDX>200d filter, hold top-10 members by 250d momentum (positive, above own 200d), EW, monthly; claimed 19.37%/0.78 Sharpe/−47% DD, 2000-2026. Replicated on the current roster (the same survivorship flavor the pitch almost certainly used — free point-in-time NDX membership does not exist): **+26.1%/1.06/−32% — BETTER than the claim, which is the indictment, not a validation.** Only 56 of 95 current members have data in 2000; a momentum RANKING on a 2026-assembled roster is a survivorship AMPLIFIER — it is a machine for "discovering" NVDA/AAPL/TSLA early because the deck contains only stocks that compounded enough to still be in the index today. Era split of the replication: 2000-09 +18.5% (vs NDX −6.7% — the trend filter dodging the dot-com collapse, real), 2010-26 +30.8% vs QQQ +19.1% (the +11.7pp "selection alpha" — this is the manufactured part: PDP, the professionally-run point-in-time version of this exact strategy family, LAGGED QQQ by 6.6pp/yr in G-months over the same era).

What's real in the pitch: the 200d index filter (a cousin of our classifier — the DD reduction vs NDX's −83% is genuine) and momentum as a concept (our French-data tests: real in both eras academically). What's manufactured: the stock-selection alpha. And even taking the pitch's own numbers at face value, it is dominated inside our ladder: −47% max drawdown is VAGG territory, and VAGG earns +32.4% there, not 19.4%; its 0.78 Sharpe sits below every tier. The genuine ingredients are already in the system in validated form (trend filter at asset-class level = the classifier; cross-sectional momentum where it survived two eras = the R-tilt). Entry 66: nothing to adopt; fourth confirmation that beating QQQ inside the G-cell via selection is a mirage that grows sharper the more biased the deck.

## Findings

1. **The 33/33/33 TQQQ/GLD/TLT mix the user read about is real but mislabeled as balanced**: +19.7% CAGR and Sortino 1.13, but −51% max drawdown and beta ≈ 1.0. Its failure mode is precisely a regime event: **2022 (−41.9%)**, when inflation broke the bond leg at the same time the levered equity leg fell — the two "ballasts" and the engine all sank together. 2008 was −34%.
2. **The QLD (2x) version dominates it risk-adjusted**: Sortino 1.19 vs 1.13, −37% vs −51% DD, at +15.3% CAGR — a better default for the same idea.
3. **Static leveraged mixes vs the indices strategy**: the 33/33 mixes earn their return from *diversified always-on leverage*; the indices strategy earns it from *timing*. Their drawdown profiles are complementary (mixes die in inflation years like 2022 [−42%] which the trend strategy sidestepped [−5%]; the trend strategy bleeds in chop like 2015-16 which the mixes shrugged off). Combining them is the obvious next test.
4. **Regime portfolios post the best headline numbers** (AGG: +22.4%, Sortino 1.11, −32%, Sharpe 0.95) but carry the design bias flag; their honest validation is forward paper trading or a pre-2007 replication with different-era ETF proxies.
5. Every leveraged-ETF result relies on the daily-reset simulation assumptions; real TQQQ tracking since 2010 is close to this model, but pre-2010 numbers are model, not history.

## Why not just VAGG the whole time? (2026-08-26)

User question after reviewing the ladder numbers. Three exhibits computed from the modern v7 engine's actual monthly returns, run through the workbook's own contribution schedule (13-stage ramp, $40k cap), after-tax convention (CAGR × 0.75 haircut − 0.6pp, then ST tax on the taxable share).

**Exhibit 1 — what the glide path costs in expectation (40y terminal wealth):**

| path | terminal (haircut + tax) |
|---|---|
| default glide (VAGG 10y → AGG 10y → MOD 15y → CONS 5y) | $41.2M |
| extended glide (VAGG to 45 → AGG to 55 → MOD after) | $89.3M |
| all-VAGG, all 40 years | $297.9M |

**Exhibit 2 — the same −49% VAGG-scale drawdown, priced in years of that age's contributions** (how long it takes to save your way back): age 30 = 3 years; 35 = 6; 40 = 13; 45 = 24; 50 = 43; 55 = 77; 60 = 141; 65 = 304. The identical percentage event transforms from a buying opportunity into an unrecoverable loss purely as the balance-to-contribution ratio grows.

**Exhibit 3 — sequence risk, isolated.** The identical 231 actual VAGG months (same CAGR, same set of returns), reordered, same contributions: crash years moved to the START (age 25-27) → $1,116M terminal; actual historical order → $43.8M; crash years moved to the END (~age 43, largest balance in a 20y window) → $16.2M. A **69× spread** from ordering alone. Early crashes are contribution-subsidized accumulation; late crashes are just losses.

**Supporting evidence against VAGG-forever, from the existing registry:** (1) out-of-sample era (pre-2007 proxies) VAGG was the worst risk-adjusted tier — Sortino 0.76, −66% maxDD — while MOD was best in BOTH eras; the modern era is the friendly sample. (2) VAGG's G-cell is 100% TQQQ; a 1987-type −22% index day is a one-day ~−66% that appears in NO leveraged backtest (the sim starts 1987-post-crash / real data 2010+). (3) Behavioral: the plan only pays if the holder executes rotations through a −49-66% at a seven-figure balance; nobody gets to assume they're the exception until they've held through one.

**Verdict — the instinct is half right, and the half matters.** Exhibits 1+3 genuinely support MORE VAGG than the default glide: while contributions dominate the balance, deep drawdowns are cheap (Exhibit 3's best case is crashes-at-start) and the expected cost of de-risking early is enormous. But Exhibit 2 is the reason "the whole time" fails: risk capacity is measured in years-of-contributions-to-recover, not in risk tolerance, and past ~age 45-50 a single in-sample-sized event costs decades of saving with the sequence-risk asymmetry now pointed the wrong way. Recommendation: extend the VAGG phase beyond the default (the VAGG-to-45 / AGG-to-55 / MOD-after path more than doubles the default glide's expectation, $89M vs $41M, while still de-risking before the years where Exhibit 2 goes vertical). The glide boundaries are Dashboard inputs — the de-risking rule to carry: step down a tier when a full VAGG drawdown would cost more years of contributions than you're willing to re-save, not at a birthday.

### Addendum — when compounding overtakes deposits, and the value of front-loading (2026-08-26)

Same engine, workbook contribution schedule verbatim. Under BOTH glide paths: a year's expected gains first exceed that year's deposits at **age 32** (balance ~$450-500k); cumulative gains exceed total contributed (incl. the $11k seed) at **age 35**. FV-at-65 of $1 deposited (extended glide): age 25 = $212, 30 = $93, 35 = $41, 40 = $18, 45 = $8, 55 = $2 — the multiplier roughly halves every 3 years early on (net 18%/yr ⇒ delay costs ~40%/yr of a dollar's terminal value in the VAGG phase). An extra $500/mo for just ages 25-27 ($18k total) adds ~$3.0M at 65 on the extended glide (166×); the identical $18k starting at 35 adds $571k, at 45 $116k. Conclusion: the deposit-maximization window is precisely now→early 30s; by mid-30s the balance is the machine and marginal deposits are second-order. Expected-value arithmetic — the front-loaded dollars also ride the full sequence-risk exposure documented above.

**Do deposits ever stop mattering?** (2026-08-27) Yes — measurably. Extended glide, terminal at 65 if deposits STOP entirely at: 45 → $71.6M (80% of the full-schedule $89.3M); 50 → 87%; 55 → 93%; 60 → 97%. Exchange rate on late dollars (terminal cost ÷ nominal cash freed): stop-at-35 = 5.0×, 45 = 2.5×, 50 = 1.9×, 55 = 1.5×, 60 = 1.2× — decaying toward 1, i.e. a dollar deposited at 60 buys barely more than a dollar. Halving (not stopping) from 45 keeps 90% of full. Mirror image of the front-loading result and of the Exhibit-2 asymmetry: past the point where you can't save your way OUT of a crash, you also can't meaningfully save your way UP. Caveat: this holds under forecast returns — in a lower-return world deposits stay the dominant lever much longer, so late-life deposit flexibility is earned by the early ramp actually happening AND returns arriving.

**End-state philosophy** (2026-08-27, user): the terminal projection is a yardstick, not a plan — no one leaves ~$90M in one account running one strategy. Expected sequence: deposits taper when the marginal multiple stops justifying them (decided with live numbers, not today); redirected cash flow diversifies into other assets (real estate, private) BEFORE withdrawals do; withdrawals price off the stop-depositing table read in reverse (~1.9× at 50, ~1.5× at 55) — a cheap premium against the real concentrated risk at scale, which is MODEL risk (one classifier, four decades), not drawdown. Structural note: monthly rotation keeps cost basis perpetually fresh, so unlike buy-and-hold there is no embedded-gain lock-in — the account is unusually cheap to peel capital out of at distribution time. The account's long-run role: the liquid, monthly-graded core sleeve of a larger balance sheet.

## Screener checkpoint frequency — how often should the classifier get to change its mind? (2026-09-01)

User request: test daily / 2-3x-week / weekly / biweekly vs the incumbent monthly. Pre-registered design: signal DEFINITION held fixed (price vs mean of prior-9 completed monthly closes — algebraically identical to the 10m rule at month-end; the SMA updates monthly, the price is checked at each checkpoint), T+1 execution, 5bp/side on traded notional, aux signals (tilt/COND/washout) stay monthly, weights re-resolve at month-ends plus intra-month flips. Monthly variant reproduces the official engine at zero cost (MOD 15.1 vs 15.3, VAGG 31.7 vs 32.4 — window-alignment rounding; all frequencies share one harness so orderings are exact). Rejection criterion stated in advance: adopt faster only if the ordering holds in both eras net of costs.

**Full v7 books, modern era (Dec 2006-Aug 2026), net of costs:**

| freq | MOD CAGR/Sortino/maxDD | VAGG CAGR/Sortino/maxDD | flips/yr | turnover/yr |
|---|---|---|---|---|
| monthly | **14.7% / 1.64 / −14.5%** | **31.3% / 1.08 / −47.1%** | 3.2 | 5.7-6.6x |
| biweekly | 12.8 / 1.44 / −16.9 | 28.0 / 0.99 / −43.4 | 4.6 | 8-9.5x |
| weekly | 13.9 / 1.60 / −12.9 | 29.0 / 1.03 / −48.4 | 6.9 | 12-14x |
| 2-3x/wk | 11.5 / 1.33 / −21.4 | 22.3 / 0.80 / −52.6 | 11.6 | 20-23x |
| daily | 12.9 / 1.50 / −17.4 | 26.9 / 0.97 / −51.6 | 16.1 | 28-32x |

**Pre-2007 era** (no daily commodity data → growth-boundary-only switch, SPY↔VUSTX, 1994-2006, with the modern era run through the identical simplified harness): monthly 14.1%/1.36 vs weekly 14.1%/1.41 vs daily 9.9%/0.99 pre-2007; monthly 9.3%/0.82 vs weekly 9.3%/0.86 vs daily 7.4%/0.69 modern. Ordering era-stable: daily and 2-3x/wk lose outright everywhere; weekly ties the boundary switch with slightly shallower DDs in both eras — but that virtue does not survive the full multi-asset book, where weekly's 2x flip rate whipsaws four cells at once and loses 0.8pp (MOD) / 2.3pp (VAGG) to monthly.

**Verdict — entry 67: keep monthly; adopt nothing.** The intuition "check at least weekly" is the one hypothesis the data respects at the boundary, and the full book still rejects it. Mechanism: price near the SMA line flips daily; monthly evaluation IS the debounce filter, and it costs almost nothing in reaction speed because the SMA itself only moves monthly. This closes the loop with entries 63-64 (the toll-booth arithmetic) from the signal side: the system is monthly because both the costs AND the signal quality say so. Operational note: running the screener more often for VISIBILITY is free and changes nothing traded — the paper logger can be run read-only any day; only the month's logged row rotates money.

## Entry at extension — "everything is already up, feels like buying the top" (2026-09-01, go-live day)

User hesitation at the first live buy: the VAGG R book looks extended. Two-part study: locate TODAY in the historical extension distribution, then condition forward SYSTEM returns (VAGG daily series, rotations included — the thing actually being bought) on entry-month extension across 108 modern R-classified month-ends, with a pre-2007 era check at the SPY boundary.

**Where today actually sits:** SPY +8.6% above its 10m SMA (61st percentile of R months — elevated, ordinary); DBC +13.0% above (81st pctile — the one genuinely stretched leg); book-weighted 6m momentum 61st pctile. And the perception check mattered: at the 6-month horizon the system trades on, GLD is −16.2% and GDX −16.0% — gold is the beaten-down slot, not the extended one, which is why the tilt already sized GDX smallest. "Feels like a top" was half data, half recency.

**Forward VAGG by entry extension (modern R months, extended = above-median):** 1m +1.1 vs +1.5%; 3m +4.8-7.0 vs +5.3-7.5% depending on metric; 6m +12.3 vs +12.5% (hit 80 vs 81%); 12m +17-21 vs +26-29%. At every horizon where waiting is an option, extension predicts nothing; the 12m gap reflects regime aging (extended months sit later in regimes; the window includes the regime's death — which the system rotates through). **Era check (SPY boundary, growth-on months): the 12m fade FLIPS — pre-2007 extended entries did BETTER (12m +19.0 vs +13.0, hit 97 vs 85%; non-overlapping windows n=7, min +7.8%); modern flat (+12.2 vs +11.6).** Extension above trend IS momentum, and momentum passed two-era validation long ago. By the registry's own standard the top-feeling is not actionable. Entry 68.

**The honest residual:** DBC at the 81st pctile is the weakest conditional cell in the modern sample (12m +11.9%, 59% hit vs +34.4% calm) and the commodity side cannot be era-checked daily pre-2006. Not adoptable as a rule (single-era, overlapping windows, ~9 effective observations) — and the system already carries the structural answer: if commodities crack, DBC loses its SMA, the month flips out of R, and the book rotates. The stop-loss is the classifier. Sanctioned responses to the feeling remain the runbook's: enter a notch lower (AGG/MOD) and step up at the next regime turn, tranche over 2-3 days; waiting in cash remains the one option no test has ever supported.

## Reflation tension — long equities AND long energy; where should the leverage sit? (2026-09-09)

User: energy rallying past some point is bearish for equities, so how can the R book be bullish both? Eventually it breaks one way. And: lever one leg, not the other? Three tests, both eras (modern 2007-2026 with QQQ/XLE/GDX/DBC; pre-2007 1987-2006 with NDX/FSENX/FKRCX/GSCI proxies).

**(A) How Reflation actually ends.** 20 modern / 30 pre-2007 R regimes. Exits: R→G (commodities break first, equities keep going) 58% / 67%; R→S (equities break first — the oil-shock path) 37% / 30%; R→D 5% / 3%. The user's fear is the MINORITY path — but it is a real conditional signal: commodity extension above its 10m SMA in the final R month before an R→S exit averaged +10.4% (modern) / +7.5% (pre-2007) vs +2.7% / +3.3% before R→G exits. High commodity extension roughly triples the odds that equities crack first. Today's DBC extension (+13% at the September stamp, +15.5% in the latest watch) sits above the pre-S average. The break month itself costs the VAGG-shape R book −3.2% (modern) / −11.4% (pre-2007) on average — paid once per R→S episode, against +1.6%/mo across all R months in both eras.

**(B) Is there a threshold where the equity leg fades while energy holds?** No, at the monthly horizon. Next-month leg returns by commodity-extension tercile, R months (n=107 / 109): HIGH tercile equity +1.29% (hit 56%) / +2.22% (hit 58%) — positive in both eras; energy +2.35% / +0.90%. Top-decile extension: modern equity +1.08% while ENERGY was the leg that faded (−1.01%); pre-2007 both +1.5%. So the equity leg keeps paying until the month it breaks, and the break shows up as a regime reclassification (S) that the monthly rotation catches. Pre-empting it is priced: the extension-gated variant (drop equity leverage when extension is top-tercile) LOST in both eras (−2.2pp / −3.6pp annualized in R months); momentum-directed leverage (lever whichever leg has stronger 6m momentum) was the worst variant everywhere (whipsaws between legs). The answer to "how can we be bullish both": the R book is not a forecast that both rise forever — it's a basket whose legs are both rewarded while both trend, and the classifier, not a forecast, resolves the tension when it breaks.

**(C) Leverage placement inside the R book, R months only (VAGG shape 30/25/25/20):**

| variant | modern ann / Sortino / maxDD | pre-2007 ann / Sortino / maxDD |
|---|---|---|
| 3x eq / 2x energy (VAGG current) | +17.5% / 0.79 / −38% | +15.4% / 0.64 / −53% |
| 3x eq / 1x energy | +14.6 / 0.76 / −33 | +13.8 / 0.63 / −48 |
| 2x eq / 2x energy | +16.3 / 0.88 / −35 | +14.2 / 0.75 / −44 |
| 2x eq / 1x energy (AGG current) | +13.3 / 0.86 / −28 | +12.5 / 0.77 / −38 |
| **1x eq / 2x energy** | **+15.1 / 0.99 / −32** | **+12.6 / 0.85 / −34** |
| 1x / 1x | +11.9 / 0.99 / −23 | +10.8 / 0.93 / −27 |

Era-stable structure: in Reflation the ENERGY leg is where leverage is efficient (it is the regime's leader) and the EQUITY leg is where leverage is inefficient (lower Sharpe in R, and it is the leg that breaks on the S-path). 1x-equity/2x-energy beats AGG's current 2x-equity/1x-energy on return AND Sortino in both eras. Full-tier impact (all regimes, engine): **AGG R → QQQ 30 + ERX/GDX/DBC tilt: +0.4pp / 0.0pp CAGR, Sortino 1.23→1.26 / 0.92→0.94, maxDD −33→−34 / −46→−44 — small, era-consistent risk-adjusted gain: CANDIDATE v8 (user decision).** VAGG R → QLD + ERX: −0.6pp in both eras for ~0 Sortino change, DD mixed (−47→−48 modern, −62→−57 pre-2007) — NO; VAGG's mandate is octane and the trade isn't there. Entry 69.

**Adopted — matrix v8 (2026-09-09).** User decision after the reflation tension study: AGG's Reflation cell becomes QQQ 30% + the ERX/GDX/DBC momentum trio (was QLD + XLE/GDX/DBC). VAGG, MOD, CONS untouched. Context: the user is holding MOD out of concern for equities with Brent at $100; the v8 AGG cell is the coherent expression of that view inside the ladder — no equity leverage in Reflation, leverage on the regime's leader. Official numbers regenerated under v8 (evidence.json / projection_stats.json / GrowthProjection.xlsx). Ledger mechanics: the September row stays v7 (append-only); the manual order tools re-resolve the September signals under v8 (flagged "restated" in the workbook header) so the AGG-v8 book can be traded this month; the October row is the first logged under v8; the automated executor reads ledger rows as-is by design. September AGG-v8 book from the logged signals: QQQ 30% / ERX 31.5% / DBC 22.75% / GDX 15.75%.

**Ops incident (2026-09-21): src/data was never in git.** `.gitignore`'s `data/` rule also matched `src/data/`, so `src/data/yahoo.py` (the price fetchers every screener imports) existed only in the original working container. Every fresh clone — the weekly Routine sessions on Sept 7/14/21 and this reprovisioned container — failed on `ModuleNotFoundError: src.data`, which is why no Routine ever pushed a watch row. Fixed: rule anchored to `/data/`, module reconstructed (granularity assertions, adjusted closes — verified to reproduce the original September boundary to the cent after the Sept ex-dividend adjustment), `market_data.py` rebuilt from its import surface. Also lost with the container: the scratchpad research caches (quadrant_prices.csv, era proxies, evidence.json). All findings and official numbers survive in TESTS.md, PORTFOLIOS.md, and GrowthProjection.xlsx; future research re-fetches from source (fetch_yahoo_daily_window exists for that).

## Drawdown anatomy — where the AGG/VAGG downside actually comes from (2026-09-23)

User: the classifier sells before major downside, so why are AGG/VAGG drawdowns −34%/−47%? Engine rebuilt in-repo (research/engine.py — reproduces official maxDDs exactly); research/drawdown_anatomy.py decomposes every top-4 drawdown by the cell in force.

**1. The signal DOES do its job in the bear markets it was built for — and those are NOT the big drawdowns.** GFC (Oct 2007–Jun 2009): AGG maxDD −13.9%, VAGG −22.7%, both finished the period UP (+27.6% / +25.2%) vs SPY −55% — the classifier moved to S in Jan 2008 and D in Oct 2008 and stayed there. COVID: VAGG −39% peak-to-trough (Feb 2020's G-month −19%, then D from March holding TMF), finished +11.5%. Neither episode makes the top four.

**2. The top-four drawdowns are all fast corrections inside a single risk-on month** — shorter than the monthly cadence can react to: Oct 2018 (VAGG −13.9%), Dec 2018 (−26.6%), Aug 2015 (−21.3%), Jan 2016 (−21.2%), Dec 2022 (−26.4%), May 2010. A −6 to −9% SPY month with 100% TQQQ is a −20 to −27% book month. The trend filter cannot fire before the damage: by the time the exit takes effect SPY is −6 to −15% from its high and the VAGG book is already −15 to −33% (2018: SPY −6.4%, book −14.6%; 2015: −9.8% / −24.9%; 2010: −15.2% / −33.1%).

**3. Whipsaw compounding is what turns a −27% month into a −47% episode.** Q4 2018 sequence: R (Oct −13.9%) → D (Nov +5.4%, exited after the damage) → G (Dec −26.6%, re-entered right before the worst month) → D. Same shape 2015-16 (Aug −21% → D → G re-entry → Jan −21%) and 2022 (S/D through the bear, then G re-entry → Dec −26.4%). The monthly SMA lags one month in BOTH directions, and 3x leverage triples the cost of every false re-entry as well as every late exit.

**Conclusion:** the classifier is a bear-market filter, not a stop-loss. It confirms trends that last quarters; it cannot anticipate corrections that resolve in weeks, and in those it loses twice (late exit, then late re-entry). Leverage multiplies both. This is the structural price of the AGG/VAGG octane and is already the reason for prior rejections: faster checkpoints (entry 67, worse net of whipsaw), intra-month crash brakes (rejected under T+1 modeling). AGG's 2x halves every intra-month hit (Dec 2018 −17.7% vs −26.6%) — that is the ladder working as designed. Every top-four episode recovered within 1-2 years; the drawdown table in dollars remains the tier-selection table.

## Can the intra-month crash months be mitigated? Breadth, momentum, volume, pacing (2026-09-23, entry 70)

User: the top drawdowns are all in the same regime cell — there must be an ex-ante tell (breadth, momentum, volume, pacing). Pre-registered: measure every risk-on month-end's ex-ante features (18-sector breadth, 1/3/6/12m momentum, extension above the 10m line, 20d realized vol, prior-month intra-month drawdown, distance from 52w high, 20d/200d volume ratio, months since re-entry) against next-month outcomes; convert any fingerprint into a DE-LEVERING rule (one notch: TQQQ→QLD, QLD→QQQ; never to cash) with absolute thresholds; adopt only if it improves both eras. Engines rebuilt in-repo (research/engine.py, research/engine_pre2007.py, transform hook) so this is reproducible.

**Modern era (188 risk-on month-ends, 13 crash months ≤ −5% SPY):** a real fingerprint. Four of the six named crash months were entered with SPY barely above its line (extension 1st-13th pctile), realized vol elevated (89th-99th for Dec 2018 / Jan 2016 / Dec 2022), breadth weak (1st-33rd); the first month after a re-entry crashes 18% of the time vs 6% baseline; high-vol tercile crashes 13% vs 3%. Two misses (Oct 2018, Feb 2020) had no warning. The composite rule (ext < 3% AND rvol20 > 16% → one notch, 15 fires) produced AGG +25.4% / 1.41 / −27% (from +24.4 / 1.25 / −34) and VAGG +33.8% / 1.23 / −41% (from +32.1 / 1.10 / −47) — higher return AND shallower drawdown.

**Pre-2007 era (184 risk-on month-ends, 8 crash months):** the fingerprint inverts on extension (crash months at the 57th pctile — entered from strength), vol only mildly elevated (65th), breadth low (31st) — and EVERY rule loses: composite −0.2/−0.3pp, breadth < 70% −2.5/−3.4pp, OR-rule −2.7/−3.9pp, re-entry-month −1.1/−1.4pp, with maxDD unchanged at −44%/−62% under all of them. Anatomy of the era-2 drawdowns: Aug 1998 (VAGG −47.5% in ONE Growth month, S&P −14.5%), Oct 1987 (−42% in a Reflation month, S&P −21.7%), Feb 1999 (−30% with S&P only −3% — NDX-specific), 1997 twice. Same anatomy as the modern era (intra-month crash inside a risk-on cell), no ex-ante tell.

**Verdict — REJECTED (era-flip), and the meta-finding is the useful part:** intra-month crash risk under leverage is not forecastable by any monthly ex-ante feature tested — the modern fingerprint is a property of the 2015-2022 correction style (grinding re-entries from weakness), not of crashes in general; 1987 and 1998 arrived from calm, extended markets. This is the fourth time a volatility/pacing conditioning has era-flipped (entries 20, 50, 67, 70). The only mitigation that holds in both eras is the leverage level itself: AGG halves every intra-month hit relative to VAGG (Dec 2018 −17.7 vs −26.6; Aug 1998 proxy −32 vs −47). The ladder IS the crash mitigation. Least-bad candidate for the file: realized vol > 25% → two notches was era-neutral (flat pre-2007, +0.7/+1.8pp modern) but never reduced a drawdown in either era — not adopted.

**Filed as a shadow (2026-09-23, user decision).** The user's structural argument — the modern era may genuinely differ (indexed, automated flows produce grinding re-entries from weakness that 1987/1998 never showed) — is the same one that put the fast-entry shadow classifier on the ledger, and it deserves the same treatment: run it alongside, cost zero, let live months decide. Wired: every ledger row now carries `fragility` (SPY extension above its 10m line, 20-day realized vol, and the fragile flag = risk-on AND ext < 3% AND vol > 16%) and, when fragile, `shadow_delever` — the AGG/VAGG books one notch down (TQQQ→QLD, QLD→QQQ). The weekly watch reports the provisional reading ("if the month ended today"). Feeds no resolution; the executor ignores it. Promotion trigger pre-registered in TESTS.md 70b: ≥6 live fragile months, shadow beats live in the majority and cumulatively → matrix rule; live wins the majority → retire. September's stamp: ext +7.9%, 20d vol 9% — not fragile.

## GDX vs GLD — is a miners ETF the right gold instrument? (2026-10-08, entry 71)

User hypothesis: GDX trades with the equity market more than with gold, and miners carry financing-cost and operating risk that bullion doesn't — so it's a poor "levered gold." Tested both eras (modern GLD/GDX/GDXJ/SLV/UGL; pre-2007 bullion proxy = CEF, the Central Fund of Canada bullion closed-end fund since 1986, miners = FSAGX / FKRCX / ^XAU). Engine: research/gold_exposure.py.

**A) What GDX actually is.** Monthly regression 2007-2026: GDX = 1.76×GLD + 0.43×SPY + 0.19×TLT, alpha **−12.5%/yr**, R² 0.73. Pre-2007: FSAGX = 0.96×CEF + 0.43×VFINX — the equity beta is the same 0.43 in both eras. GDXJ is worse (2.04×GLD + 0.58×SPY, alpha −14%). The miners-minus-bullion spread loads 0.52 on SPY and 0.45 on TLT (modern) — it widens when stocks rally and when rates fall, which is exactly the financing-cost sensitivity the user described. The cost of that package shows in the tail: in SPY-down-≥3% months, GLD averaged +0.8% and GDX −2.0% (modern); CEF +0.7% vs FSAGX −2.9% (pre-2007). The hedge-like property of gold is what the miners wrapper throws away.

**B) In the Reflation slot specifically** (modern, n=112 R months): GLD +1.07%/mo, Sharpe 0.75; 2x gold +1.84%/0.65; GDX +0.80%/0.28; GDXJ +0.35%/0.11; SLV +1.22%/0.46. GDX earns less than bullion with 2.5x the risk. (Miners' one strong regime is Deflation — +5.9%/mo, Sharpe 1.22 — but the D cells already hold GLD by an earlier user decision and the UGL-in-D variant was rejected in entry 57.)

**C) Full-tier impact, R cell GDX → GLD with the tilt on GLD's own momentum:**

| | modern AGG | modern VAGG | pre-2007 AGG | pre-2007 VAGG |
|---|---|---|---|---|
| current (miners) | +24.4% / 1.25 / −34% | +32.1% / 1.10 / −47% | +21.2% / 0.94 / −44% | +25.8% / 0.75 / −62% |
| **bullion (v9)** | **+25.2% / 1.34 / −33%** | **+33.1% / 1.16 / −47%** | **+21.5% / 0.97 / −43%** | **+26.3% / 0.78 / −60%** |
| 2x bullion | +26.3 / 1.37 / −34 | +34.3 / 1.19 / −47 | +20.7 / 0.91 / −49 | +25.5 / 0.75 / −63 |

Bullion improves CAGR, Sortino AND drawdown in both eras — small pre-2007, moderate modern — the standard for adoption. 2x bullion is the modern winner but loses pre-2007 (era-flip; same verdict as entry 57's UGL test; UGL real does track the 2x simulation at corr 0.999, so the simulation isn't the problem — leverage on a slot that had a weak pre-2007 Reflation leg is).

**Honest caveat:** the year-by-year difference runs against the swap in the two most recent years — miners beat bullion by ~12pp in 2025 and ~6pp in 2026 YTD (the full-sample gains come from 2011, 2013, 2020, 2023). A regime of miner outperformance is live right now; the full-sample and era-2 answer is still bullion. **CANDIDATE v9 — AGG/VAGG Reflation cell GDX → GLD, tilt trio ERX/GLD/DBC (matching MOD's XLE/GLD/DBC). User decision.**

## GDX vs GLD, cell by cell — the regime decides the instrument (2026-10-08, entry 72)

User: "It's perfectly fine to have GLD in some places and GDX in others. That's the point of the model." Tested every gold-holding cell in both eras (research/gold_by_cell.py): the cell's gold slot set to bullion or miners with everything else fixed; cell-month Sharpe and full-tier stats. Pre-2007 bullion = CEF, miners = FSAGX; note the legacy era-2 engine had used FKRCX (a miners fund) as its "gold" in the CONS/MOD/D cells, so this test also makes bullion-vs-miners explicit everywhere.

| cell | now | modern: miners − bullion (full-tier Sortino / CAGR) | pre-2007 | verdict |
|---|---|---|---|---|
| CONS G | GLD | −0.21 / −0.3pp | −0.01 / +0.2pp | bullion |
| CONS R | GLD | −0.29 / −0.2pp | −0.17 / −0.2pp | bullion |
| CONS D | GLD | −0.15 / +1.6pp (maxDD −10→−18%) | +0.14 / +0.8pp | split → keep GLD (mandate) |
| MOD R | GLD | −0.30 / −0.4pp | −0.12 / −0.2pp | bullion |
| MOD D | GLD | −0.07 / +1.9pp (maxDD −14→−23%) | +0.10 / +1.0pp | split → keep GLD (drawdown) |
| AGG R | **GDX** | −0.09 / −0.8pp | −0.03 / −0.3pp | **bullion** |
| AGG D | GLD | +0.08 / +2.1pp (DD unchanged) | +0.04 / +1.0pp | **miners** |
| VAGG R | **GDX** | −0.06 / −1.0pp | −0.02 / −0.4pp | **bullion** |
| VAGG D | GLD | +0.06 / +2.2pp (DD unchanged) | +0.03 / +1.1pp | **miners** |

**The mechanism is the model's own logic.** Miners = bullion + 0.43 equity beta + rate sensitivity (the miners-minus-bullion spread loads 0.45 on TLT) − carry. In Reflation (stocks up, commodities up, rates rising) the equity beta is redundant with the book's equity leg and the rate sensitivity and carry are headwinds — bullion wins. In Deflation (stocks down, rates falling) the rate sensitivity flips to a tailwind, gold's rally is amplified by operating leverage, and the equity beta is small next to the cell's TLT/TMF — miners win: Deflation-month miners +26-51%/yr annualized across tiers vs bullion +14-36%, in both eras. The two defensive tiers can't afford the drawdown that comes with it (CONS −10→−18%, MOD −14→−23%); the two aggressive tiers get it for free (maxDD unchanged).

**Combined candidate v9 (AGG/VAGG only):** Reflation gold slot GDX → GLD with the tilt trio ERX/GLD/DBC; Deflation gold slot GLD → GDX at the same 30%. Full-tier: modern AGG +24.4 → 27.3% / 1.25 → 1.41 / −34 → −33; VAGG +32.1 → 35.3% / 1.10 → 1.22 / −47 → −47; pre-2007 AGG +21.2 → 22.1 / 0.94 → 1.00 / −44 → −43; VAGG +25.8 → 26.9 / 0.75 → 0.79 / −62 → −60. All three metrics improve in both eras. Where it comes from: 2020 (+20/+25pp — miners in the March-May 2020 Deflation months), 2011/2013/2016/2023 (bullion in Reflation). Where it loses: 2024-2026 (−3/−10/−5pp — miners have beaten bullion in recent Reflation months). CONS/MOD unchanged. Supersedes the entry-71 single-cell candidate. User decision.

**Adopted — matrix v9 (2026-10-08).** AGG/VAGG Reflation gold slot GDX → GLD (tilt trio ERX/GLD/DBC); AGG/VAGG Deflation gold slot GLD → GDX (30%). CONS/MOD unchanged. Official numbers regenerated with the in-repo engine (research/official_stats.py → evidence_current.json; GrowthProjection.xlsx patched in place by research/update_projection_xlsx.py; window Jan 2007–Sep 2026): CONS +9.8% / 1.62 / −10.2%; MOD +15.4% / 1.73 / −14.3%; **AGG +27.3% / 1.41 / −33.1%; VAGG +35.3% / 1.22 / −46.8%**; SPY +11.0% / 0.69 / −55.2%. Ledger: the October row stays v8 (append-only); the manual order tools restate it under v9 — the October AGG book becomes QQQ 30 / DBC 31.5 / ERX 22.75 / GLD 15.75 (one line changes: GDX → GLD). November's row is the first logged under v9.

## ERX on the same premises — energy instrument by cell (2026-10-08, entry 73)

The natural follow-up to entry 72: is 2x energy equities the right instrument in every cell that holds energy, or does the regime want 1x, the commodity itself, or levered oil? Same design (research/energy_by_cell.py): each Reflation cell's energy slot set to XLE / ERX / USO / 2x-USO (pre-2007: FSENX / 2x / GSCI / 2x GSCI) with everything else fixed at v9; each Stagflation cell's short slot set to ERY (2x inverse energy equities, current) / 1x inverse / SCO (2x inverse oil); full-tier and cell-month stats, both eras.

**What energy equities are**: XLE = 0.27×oil + 0.82×S&P (R² 0.55); pre-2007 FSENX = 0.57×GSCI + 0.77×S&P. Unlike miners-vs-gold, the equity beta here is not a defect to engineer around — it is most of the exposure, and in Reflation (stocks up) it is on the right side. In S&P-down months XLE loses with the market (−6.3% vs −6.6%) while oil loses less (−5.6%) and pre-2007 GSCI actually rose (+1.2%) — but that tail only matters in regimes where the book doesn't hold XLE.

**Result — no change, in any cell, in either era.** Reflation: the commodity itself (USO/GSCI) is worse than energy equities everywhere (Sortino −0.04 to −0.15, CAGR −0.3 to −2.1pp, both eras); 2x oil worse still. Leverage placement confirmed in both directions: 1x is right for CONS/MOD (ERX costs Sortino −0.18/−0.23 and −0.19/−0.15 and widens drawdowns 3-8pp), 2x is right for AGG/VAGG (XLE costs −0.05/−0.02 and −0.03/−0.01 with −0.8 to −1.5pp CAGR). Stagflation short: ERY vs a 1x inverse is a wash (±0.02 either way — era-split at the noise floor); SCO (shorting oil instead of energy equities) is worse in both eras. ERX real tracks the 2x simulation at corr 1.000 since its March-2020 leverage cut, so the simulation is not the question. The v8 decision (lever energy, not equities, in Reflation) and the v6 short book are both re-confirmed on the v9 baseline.

## Business-cycle sector rotation vs the regime model (2026-10-20, entry 74)

User: a piece of research on longing the right assets AND the right industries at the right point in the business cycle (the Fidelity early / mid / late / recession framework). Tested on our own terms (research/cycle_sectors.py, cycle_sectors_impact.py): phases defined ex-ante from the classifier (recession = S/D; early = first 4 risk-on months after an exit; mid = Growth after that; late = Reflation after that), Fidelity's leader/laggard map applied literally, SPDR sectors modern and the 16 Fidelity Select funds pre-2007.

**The sector map, era by era (annualized excess vs the broad market):**

| phase | n (mod/old) | what led, both eras | what lagged, both eras | Fidelity leaders − laggards spread |
|---|---|---|---|---|
| early | 54 / 45 | **tech** (+10.5% / +28.3%) | financials (−6.6% / −6.1%), energy, utilities | +1.4% / +2.2% (Sharpe 0.14 / 0.17) |
| mid | 48 / 50 | tech, financials, industrials, discretionary | staples, utilities, energy | **+9.3% / +11.5%** (1.06 / 1.08) |
| late | 87 / 88 | **energy** (+15.1% / +9.3%), utilities, staples | tech (+1.9% / −8.1%), discretionary, real estate | **+5.8% / +6.8%** (0.56 / 0.62) |
| recession | 49 / 56 | cyclicals (tech modern; industrials/materials/RE pre-2007) | utilities, financials modern | **−9.9% / −6.3%** (backwards) |

Three readings. (1) Where the map overlaps the book it is right and the book already holds it: mid-cycle = tech = our Growth cell (QQQ/QLD/TQQQ); late-cycle = energy = our Reflation cell (XLE/ERX, the grid's #1 both eras in August's screen too). (2) Fidelity's early-cycle claim — financials, industrials, real estate lead the first stretch after a recession — fails in both eras; the early phase is led by tech and discretionary. (3) Their recession-defensives claim is backwards under a trend-defined regime: our S/D months are classified AFTER the decline, so they carry early-cycle leadership (the same finding as August's D-cell screen). A macro-indicator phase clock would call the recession earlier than our price clock does — which is exactly the lead the classifier cannot have (entries 44-52: every macro early-warning signal era-flipped).

**Impact, leverage-matched (daily-reset simulated sector baskets):** replacing every cell's equity leg with the phase basket era-splits badly (modern AGG 27.4→19.6%, VAGG 35.2→23.9% — an equal-weight tech+industrials basket cannot keep up with QQQ in the AI era; pre-2007 +1.5/+4pp). The one targeted variant the grid supports — late-phase Reflation months only, equity leg → the late basket (energy/materials/healthcare/staples/utilities) — improves AGG and VAGG on CAGR and Sortino in both eras (AGG +0.2/+0.7pp, Sortino +0.01/+0.02; VAGG +1.0/+2.9pp, +0.04/+0.09) with drawdowns flat, but MOD era-splits on Sortino (1.74→1.81 modern, 1.40→1.36 pre-2007), and the AGG/VAGG gains are earned by 2x/3x sector baskets that do not exist as liquid products (no levered healthcare/staples/utilities ETFs worth holding). Disclosed: this was the third variant of one hypothesis.

**Verdict — NOT adopted; filed.** The late-phase sector effect is real and era-stable at the sector level, but the tier where it is implementable (MOD, 1x) is era-split, and the tiers where it tests well cannot trade the instrument it requires. If levered sector baskets become available, or if the live ledger accumulates enough late-phase Reflation months to re-test MOD forward, revisit. The durable takeaways: the model already owns the two phase-sector effects that survive two eras (tech in Growth, energy in Reflation), and the framework's other two claims (early-cycle financials, recession defensives) do not survive a trend-defined calendar. Entry 74.

## Swing trading — does any of this work day-over-day or week-over-week? (2026-11-14, entries 75-78)

User question: the regime model and its research are monthly; is any of it useful for swing trading, including ETF options, with Bollinger bands tested alone and combined? Code: `research/swing/` (data, lib, strategies, study_daily, study_sleeve, study_weekly, study_options, study_extras, study_checks). Data: adjusted daily OHLC for 30 ETFs (broad, 9 SPDR sectors, 7 sub-sectors, gold/silver/miners, bonds, commodities, international) plus vol indices, 1993/1999-2026. Eras: A 1999-2006, B 2007-2016, C 2017-2026, with a 1987-98 index-only check. Signals use the close; entry at that close (next-open checked); 5bp per side; one position per asset.

**1. Daily dip-buying is a real, era-stable edge on equity ETFs.** Net bp per trade, pooled 30 ETFs:

| signal | hold | all | A 99-06 | B 07-16 | C 17-26 | win |
|---|---|---|---|---|---|---|
| Bollinger(20,2) close below lower band → exit above mid | 8.1d | +28 | +33 | +10 | +45 | 59% |
| same + price above 200d SMA | 7.8d | +52 | +43 | +51 | +57 | 65% |
| RSI(2)<10 + 200d trend → exit above 5d SMA | 3.8d | +26 | +28 | +28 | +24 | 69% |
| IBS<0.2 → exit above prior high | 3.2d | +21 | +10 | +21 | +26 | 64% |
| Bollinger + IBS<0.2 | 8.2d | +45 | +51 | +34 | +56 | 60% |
| Bollinger + RSI(2)<10 → exit above 5d SMA | 4.1d | +26 | +41 | +26 | +18 | 66% |
| Bollinger upper-band breakout | 16d | +25 | −0 | −13 | +73 | 39% |

15 of 18 Bollinger grid cells (N 10/20/30 × K 1.5/2/2.5 × two exits) are positive in all three eras; the three exceptions are 2.5-sd bands with one negative era each. By asset group the edge lives in equities (broad +41bp, sectors +42bp, sub-sectors +45bp for plain Bollinger) and is absent or negative elsewhere: bonds −3bp, commodities −82bp (DBC/USO trend; dips keep going), gold only with the trend filter. 1987-98 index check is also positive (S&P RSI2+200d +49bp, t 3.9), even though daily autocorrelation only turned negative after 2000.

**2. The regime model is the best filter found.** "Aligned" = the asset group is one the rotation book is long in the quadrant in force (equities in G/R, energy in R, gold in R/D, bonds in D, commodities in R):

| Bollinger dip-buy | all | A | B | C |
|---|---|---|---|---|
| aligned (n=2,466) | **+44bp** | +54 | +39 | +46 |
| not aligned (n=1,160) | −6bp | +5 | −47 | +42 |

Same split for Bollinger+RSI2 (+41 vs −6) and RSI2+trend (+28 vs +13). Subtracting what the asset earns anyway in that regime (days held × its mean daily return in the same era and quadrant), the aligned-equity edge that remains is +19bp (Bollinger), +16bp (RSI2+trend), **+34bp (Bollinger+RSI2, cluster-t 5.6, positive all eras)**, and ≈0 for IBS alone. Breakouts are −61bp vs drift. The edge concentrates in high-vol dips: VIX≥25 trades earn +111bp (Bollinger), +91bp (RSI2), +75bp (IBS), all eras; VIX<16 trades earn +14bp, +11bp and +1bp.

**3. As a sleeve next to the book it fails the adopt rule.** Four slots, most-oversold first, equity ETFs, aligned gate: 40 trades/yr, 16% average exposure, +3.5%/yr on sleeve capital, sleeve maxDD −7/−18/−16% by era. On the live AGG book, 2007-2026:

| | CAGR | Sortino | maxDD |
|---|---|---|---|
| AGG core | +27.4% | 1.42 | −33.1% |
| + 25% margin overlay | +27.8% | 1.38 | −35.3% |
| + 50% margin overlay | +28.2% | 1.34 | −37.6% |
| + 100% margin overlay | +28.9% | 1.25 | −42.7% |
| 20% carve-out (idle sleeve in bills) | +22.8% | 1.42 | −29.1% |

Same sign on CONS, MOD and VAGG, and in both halves on AGG. The sleeve's daily correlation to the core is +0.39 and it loses −52bp on the core's worst 5% of days: dip-buying adds beta exactly when the book is drawing down. Restricting to VIX≥20 is the closest to neutral (+1.2pp CAGR at 50%, Sortino 1.40, maxDD −36.6%) but still does not improve every metric. Cost sensitivity: at 10bp/side (IBKR fixed pricing's $1 minimum on ~$1,100 slots is 9bp) the 50% overlay adds +0.1pp. In dollars at $17.5k, a 25% overlay is worth roughly $70/yr before tax.

**4. Week-over-week: nothing.** Sector rotation by 1w/4w/13w/26w momentum loses to equal-weight sectors in every era; 1-week reversal is flat then −7.5pp/yr in 2017-26; the regime gate rescues neither. Weekly Bollinger lower-band buys and breakouts are positive raw but at or below drift. Crash weeks (−8% or worse) are followed by +256bp over four weeks vs +76bp unconditional, but only +59bp in 2007-16.

**5. Options (model-based — Black-Scholes on VIX/VXN, no historical chains).** The wrapper gives back most of the edge: SPY/QQQ aligned Bollinger+RSI2 dips earn +72bp on stock, +14bp of notional through an ATM call, +25bp through a 0.96 ITM call, +11bp through put credit spreads. Theta (~4bp/day on a 30-DTE ATM option) and the ~1pt IV decline into the bounce eat it. On risk capital the SPY/QQQ structures are positive in all three eras (call debit spread +7.0%/trade, t 3.4; 0.97/0.92 put credit spread +2.6%, sd 8%, t 4.6; about 7 trades a year). Sector-ETF options are negative in every era: one-cent half-spreads plus $0.65/contract on a $25-80 underlying cost about what the signal earns. Filed with the existing options item; needs real chains.

**6. Side results.** Sector short fades: +65bp in growth-off quadrants but −5bp in 2017-26 — no. Fragile state (S&P 0-3% above its 200d with 20d vol above 16%): Bollinger dip-buys −241bp, negative in all three eras, n=77 over 28 distinct weeks — small, but it independently matches the fragility shadow's fingerprint (entry 70b). Levered ETFs on the same signals are just leverage (QQQ signal → TQQQ +230bp/trade, worst −19%). Waiting up to 10 days for a dip to deploy a contribution: no gain, negative in 2017-26.

**Verdict.** The research transfers in one direction: the quadrant model tells you which dips are worth buying (aligned assets, growth on, not fragile, elevated VIX), and that is a statistically solid, era-stable result. It does not transfer into a better portfolio: the edge is ~35bp a trade a few dozen times a year, it arrives correlated with the book's own drawdowns, and every way of funding it (margin, carve-out, options) either worsens risk-adjusted results or hands the edge to costs. No sleeve adopted; no matrix or process change. If swing trading is wanted as an activity anyway, the tested-best form is: Bollinger(20,2) lower-band close with RSI(2)<10 on SPY/QQQ/sector ETFs the book is long that month, skip the fragile state, exit above the 5-day SMA or after 10 days, stock rather than options, ≤25% of equity, IBKR tiered pricing.

### Addendum — the swing strategy as its own account (2026-11-14, entry 79)

User correction: the swing idea is a separate account, not a layer on the portfolio, so it is assessed standalone here. Correlation with the rotation book and the adopt rule for matrix changes do not apply. Code: `research/swing/study_standalone.py`, `study_standalone_checks.py`. The account holds T-bills until a signal fires, then buys up to N equity ETFs; daily account returns include costs and bill interest on idle cash.

**Design search (48 designs, ranked by worst-era Sharpe, not best fit).** Signals: Bollinger+RSI2, RSI2+200d trend, and their union. Universes: SPY+QQQ or 20 equity ETFs. Slots 1/2/4. Gates: none, regime-aligned (Growth/Reflation months only), aligned + not fragile. Findings: (a) SPY+QQQ beats the 20-ETF universe at the account level in every gate — with few slots the wide universe concentrates in single sector dips and 2017-26 goes to roughly zero; (b) the regime gate costs about a point of return and removes much of the downside (union signal, two slots: CAGR +7.3% → +6.3%, maxDD −22% → −14%, worst year −12% → −7%, Sharpe 0.72 → 0.87); (c) all 18 SPY+QQQ designs are positive in all three eras.

**Selected design.** SPY and QQQ. Buy at the close when RSI(2) < 10 and the close is either below the lower Bollinger(20,2) band or above the 200-day SMA; only when the quadrant in force is Growth or Reflation; not when the S&P is 0-3% above its 200d with 20d vol above 16%. Exit at the first close above the 5-day SMA, or after 10 trading days. Two slots of 50%.

| 1999-2026 | CAGR | Sharpe | maxDD | worst year | positive years | A 99-06 | B 07-16 | C 17-26 |
|---|---|---|---|---|---|---|---|---|
| selected, 1x | +6.3% | 0.87 | −14% | −7% | 89% | +8.3% | +3.8% | +7.2% |
| selected, 2x ETFs | +9.9% | 0.71 | −27% | −16% | 89% | +12.7% | +6.4% | +11.3% |
| selected, 3x ETFs | +13.1% | 0.67 | −38% | −25% | 89% | +16.8% | +8.6% | +15.0% |
| SPY buy & hold | +8.5% | 0.52 | −55% | −37% | 79% | +2.7% | +6.9% | +14.9% |
| QQQ buy & hold | +10.5% | 0.51 | −83% | −42% | 79% | −2.2% | +11.6% | +20.2% |
| T-bills | +2.0% | | | | | +3.2% | +0.6% | +2.5% |

Invested 11% of days (some position on 15% of days), 16 trades a year, 438 trades: +55bp mean, 72% win, average win +1.36% vs average loss −1.54%, worst −10.0%, longest losing streak 4. Excess over T-bills +4.35%/yr on 7.3% vol: excess Sharpe 0.59, t 3.1 over 27 years (0.66/0.49/0.64 by era). Capital earns about 41% annualized while deployed; the constraint is how rarely it is deployed.

**Checks.** Entry at next open instead of the signal close: +5.0% (2x +7.4%). Costs 10bp/side: +5.4%; 20bp: +3.8%. Parameter neighbours (RSI threshold 5/10/15/20 × exit SMA 3/5/8): all 12 positive in every era, CAGR +4.0% to +7.6%. Extra era, SPY only 1994-1998: +11.2%, Sharpe 1.47, n=45, 80% win. Losing years: 2011 −7.4%, 2018 −5.0%, 2016 −0.1%. Yearly correlation with SPY +0.26.

**Options version (model-based).** Same signal through 30-DTE SPY/QQQ options, risking 10% of the account per trade: call debit spread +6.8%/yr with −39% trade-level drawdown, ATM call +6.0%/−45%, put credit spreads +2.4%/−17% (before bill interest). Levered ETFs deliver more return per unit of drawdown than any option structure modelled, without the model risk.

**Assessment.** As a standalone strategy it is real and small: a statistically solid +4% a year over cash at 1x with shallow drawdowns, scalable to roughly +10% (2x) or +13% (3x) with drawdowns of −27% and −38%. It beat SPY buy-and-hold over the full 27 years only with leverage, and lagged it in the 2017-26 bull decade at any leverage tested. Its strengths are the drawdown profile, the low time in market, and that it needs one decision a day. Its weaknesses are capital idleness, short-term tax treatment on every gain, and dependence on a mean-reversion regime in index returns that has existed since the mid-1990s but is not guaranteed. Not adopted or rejected — it is a user decision whether to run it, at what leverage, and with how much capital.

### Addendum 2 — short-horizon band bounces, tight stops, and fading stretched moves (2026-11-14, entries 80-82)

User clarification: the idea is shorter-term and more aggressive than entry 79 — catch the bounce off a Bollinger band on a short chart (a "3-day view"), sell at the top band, use leverage and tight stops — plus a check on swing-trading our own signals when energy, the S&P or another model asset is over-stretched or sold off hard. Code: `research/swing/intraday_data.py`, `study_bounce.py`, `study_bounce2.py`, `study_stretch.py`, `study_selloff_account.py`. "3-day view" was tested under both readings: intraday bars on a multi-day chart (5m, 15m, 60m) and 3-day bars. Free intraday history is short — 60 days for 5m/15m, 2 years for 60m — so the intraday tables are indicative and the daily tables (27 years) carry the weight.

**The bounce trade, one simulator at every bar size.** Entry: price trades down to the prior bar's lower band (20, 2). Exit: stop, else the upper band, else a time stop. Net of costs.

| bars | history | no stop | 2% stop | 1% stop | 0.5% stop |
|---|---|---|---|---|---|
| 5-minute | 42 days | −13bp | −11bp | −11bp | −12bp |
| 15-minute | 42 days | −43bp | −32bp | −30bp | −17bp |
| 60-minute | 2 years | **+19bp** (61% win, t 1.9) | +7bp | −3bp (36% win) | −4bp (22% win) |
| daily, 20 equity ETFs | 27 years | **+40bp** (+36/+54/+26 by era) | −2bp | −3bp (19% win) | |
| 3-day bars | 27 years | **+138bp** over ~20 days | | 3% stop +48bp, era-unstable | |

The stop is the failure point, not the band. A mean-reversion entry is by construction made into weakness; the first thing price does is wiggle lower, and a stop inside that wiggle sells the low. Three rescues were tested and failed: (1) waiting for the first close back inside the band and stopping under the excursion low — negative in all three eras on daily bars (−10bp), flat on hourly; (2) volatility-scaled stops — negative at 0.5-1 ATR, zero at 2, positive only at 5 ATR where 8% of trades touch it; (3) leverage, which requires a proportionally tighter stop on the underlying — TQQQ on hourly bars with a 1% stop wins 16% of the time.

**The intraday band is entry timing, not a signal.** Hourly lower-band touches earn +71bp (69% win, n=98) when the prior daily bar was sold off (daily RSI2<10 or below the daily lower band) and +7bp when it was not. Over the same two years and ETFs, buying the daily close on that daily signal earned +100bp with an 80% win rate. Shorting upper-band touches on sectors, gold, oil and bonds lost 23-35bp on hourly bars.

**Stretched and sold-off model assets (daily, 1999-2026).** z5 = 5-day return in units of its own volatility; event = first close beyond ±2.

| long the sell-off (z5 < −2) | n | mean | win | by era | above trend line | below |
|---|---|---|---|---|---|---|
| S&P / Nasdaq | 184 | +111bp | 76% | +180 / +107 / +74 | +85 | +138 |
| sectors ex-energy | 1,044 | +65bp | 71% | +97 / +90 / +25 | +79 | +53 |
| energy equities (XLE) | 97 | +23bp | 74% | +101 / +79 / −70 | **+65** | −5 |
| oil (USO) | 80 | −52bp | 64% | — / +5 / −89 | **+124** | −132 |
| broad commodities (DBC) | 77 | −4bp | 60% | — / −9 / +2 | **+88** | −44 |
| gold | 63 | +51bp | 65% | +45 / +5 / +93 | **+119** | −9 |
| miners / silver | 126 | +71bp | 61% | +34 / +49 / +96 | **+160** | +30 |
| long bonds | 67 | +41bp | 66% | −46 / +57 / +59 | +47 | +39 |

Trend line = the 210-day SMA, the daily twin of the model's 10-month dial. Equities bounce from sell-offs in any state; real assets bounce only while their trend is intact — the same asymmetry the daily Bollinger study found for commodities. Fading strength does not work: shorting z5 > +2 earns 0bp on sectors, −13bp on energy, −25bp on gold, −9bp on bonds; the S&P's forward 5-day return after a stretch is 38bp ABOVE average; the trend dial at its own 97th percentile has no stable forward sign. Oil shorts on a stretch outside Reflation made +229bp but on 28 trades with a −32% worst case.

**Standalone account v2 (entry 82).** Entry 79's SPY/QQQ dip-buy under the regime gate, plus z5 sell-off entries on XLE, GLD, GDX, TLT, DBC and USO when above their trend line; exit above the 5-day SMA or after 10 days; two 50% slots; T-bills when idle.

| 1999-2026 | CAGR | Sharpe | maxDD | worst year | A 99-06 | B 07-16 | C 17-26 |
|---|---|---|---|---|---|---|---|
| entry 79 (SPY/QQQ only), 1x | +6.3% | 0.87 | −14% | −7% | +8.3% | +3.8% | +7.2% |
| v2 combined, 1x | **+8.4%** | 0.99 | −14% | −5% | +9.1% | +5.3% | +11.2% |
| v2 combined, 2x | **+14.1%** | 0.85 | −26% | −14% | +14.3% | +9.1% | +19.1% |
| v2 combined, 3x | **+19.3%** | 0.81 | −38% | −23% | +19.3% | +12.7% | +26.5% |
| v2 at 3x with a 5% stop | +16.4% | | −42% | | | | |
| v2 at 3x with a 1% stop | +5.9% | | −47% | | | | |

20 trades a year, +64bp per trade, 73% win, invested 15% of days. Caveats: this is the best of nine designs; the non-equity legs are thin (16-33 trades each since 2006) and XLE's leg is negative in 2017-26; levered-ETF returns are modelled (daily N× minus financing and expense), not real fills.

**Verdict.** Shorter-term and higher leverage are compatible with the evidence; tight stops are not — they are the single most reliably destructive element tested in this study, at five bar sizes and with three stop constructions. Risk control for a bounce strategy has to come from position size, the time stop, the regime gate and the trend-line filter. The band on a short chart is useful only as a way to enter a trade the daily chart has already justified. On the second question: our signals support buying hard sell-offs (equities always, real assets only above their trend line) and do not support fading stretched rallies.

### Addendum 3 — buy triggers only, SPY and QQQ (2026-11-14, entry 83)

User request: forget the exit; which sell-off size or Bollinger condition on SPY or QQQ should trigger a buy, on horizons from intraday to one week. Code: `research/swing/study_triggers.py` (60 triggers; SPY 1993-2026, QQQ 1999-2026, daily OHLC; hourly bars for 2024-26). Each trigger is scored by the mean return from the fill to the same-day close (intraday triggers), the next day, 3 days and 5 days; the 5-day win rate; the average and 1-in-20 worst low over the next 5 days ("heat"); and the best high over the next 5 days. Intraday level triggers are filled at the level, or at the open if the price gaps through. Baseline any day: SPY +0.05% next day, +0.23% over 5 days; QQQ +0.05% / +0.26%.

| SPY trigger | days/yr | next day | 5 days | 5d win | avg heat | 1-in-20 heat | eras positive |
|---|---|---|---|---|---|---|---|
| close below lower band (20,2) | 12.9 | +0.32% | +0.80% | 64% | −2.3% | −8.4% | 4/4 |
| 2nd+ straight close below band | 5.4 | +0.33% | +1.11% | 71% | −2.4% | −8.3% | 4/4 |
| close ≥1% below the band | 2.8 | +1.04% | +1.36% | 67% | −3.6% | −10.8% | 4/4 |
| close ≥2% below the band | 1.0 | +1.87% | +2.56% | 71% | −5.2% | −14.9% | 3/3 |
| below band and above 200-day avg | 6.7 | +0.28% | +0.91% | 66% | −1.5% | −5.6% | 4/4 |
| 1-day drop ≥2% | 10.0 | +0.33% | +0.83% | 60% | −3.3% | −9.8% | 4/4 |
| 3-day drop ≥5% | 3.1 | +0.97% | +1.59% | 62% | −4.4% | −13.3% | 4/4 |
| 5-day drop ≥5% | 5.5 | +0.55% | +1.33% | 64% | −4.2% | −13.1% | 4/4 |
| 5-day drop ≥2 sigma | 7.6 | +0.37% | +0.93% | 67% | −2.7% | −9.6% | 4/4 |
| 4 down closes in a row | 8.1 | +0.43% | +1.11% | 71% | −1.8% | −5.8% | 4/4 |
| RSI2 < 2 | 3.9 | +0.52% | +1.24% | 70% | −2.3% | −8.3% | 4/4 |
| intraday: 3% below the day's open | 3.8 | +1.25% | +1.65% | 65% | −4.6% | −13.9% | 4/4 |

| QQQ trigger | days/yr | next day | 5 days | 5d win | avg heat | 1-in-20 heat | eras positive |
|---|---|---|---|---|---|---|---|
| close below lower band (20,2) | 12.5 | +0.43% | +1.06% | 62% | −2.8% | −9.3% | 3/3 |
| 2nd+ straight close below band | 5.3 | +0.58% | +1.48% | 66% | −2.4% | −8.7% | 3/3 |
| close ≥1% below the band | 3.6 | +0.90% | +2.00% | 67% | −3.8% | −15.2% | 3/3 |
| close ≥2% below the band | 1.3 | +1.72% | +3.42% | 76% | −4.0% | −12.9% | 3/3 |
| below band + 1-day drop ≥1.5% | 7.6 | +0.58% | +1.44% | 64% | −3.2% | −11.3% | 3/3 |
| 3-day drop ≥5% | 9.2 | +0.67% | +1.37% | 62% | −4.8% | −14.7% | 3/3 |
| 5-day drop ≥7% | 7.3 | +0.82% | +1.42% | 63% | −5.0% | −14.2% | 3/3 |
| 5-day drop ≥10% | 2.7 | +2.04% | +2.12% | 65% | −5.1% | −14.3% | 3/3 |
| 5-day drop ≥2 sigma | 7.3 | +0.59% | +1.29% | 64% | −3.1% | −10.7% | 3/3 |
| 5 down closes in a row | 3.6 | +1.20% | +1.70% | 69% | −2.1% | −6.1% | 3/3 |
| RSI2 < 5 | 12.5 | +0.61% | +1.08% | 62% | −2.6% | −8.2% | 3/3 |
| 1-day drop ≥2% (weak) | 21.8 | +0.23% | +0.63% | 56% | −4.2% | −11.9% | 3/3 |

Readings. (1) The Bollinger band works best as a closing condition, and depth below the band is the dose: the bounce roughly doubles from "below" to "1% below" and again to "2% below". (2) Repeat closes below the band are better entries than the first one — the first is often the start of the move. (3) Multi-day sell-offs beat single-day drops, especially for QQQ, where one-day falls of 2-4% carry almost no extra information. (4) Volatility-scaled 5-day drops and down-day streaks give similar returns with less heat than raw percentage triggers. (5) Intraday triggers have no same-day bounce: buying 1%, 2%, 3% or 4% below yesterday's close returns 0.0-0.3% to that day's close in SPY and QQQ, the hourly band touch returns 0.00%, and "2-3% off the day's high" closes lower than the fill more often than not; the gain comes on days 1-5. Waiting for the close costs nothing on average. The one intraday trigger with a same-day bounce in every era is SPY trading 3% below its own open (+0.86% to the close). (6) Triggers that are not triggers: closing back above the band (+0.17% / +0.13%), QQQ gap-downs, one-day sigma shocks. (7) Every trigger takes heat first: the average worst low over the next five days is 2-6% below the fill and one case in twenty is 8-16% below, which is the arithmetic behind the stop results in entry 80.

## Trend & Cycle / Quadrant Balances — the real tool, rebuilt from the user's workbook (2026-11-21, entry 84)

The user pointed out that my "fragile" flag and four-phase snapshot were not their old desk's tool, and supplied an Optuma workbook (dated 2026-11-20). It shows what entries 53-55 only approximated. Code: `src/portfolio/trend_cycle.py` (module + CLI + weekly log `paper/trend_cycle.csv`), `tests/test_trend_cycle.py`, `research/trend_cycle/study_states.py`.

**What it is.** Two oscillators computed on daily, weekly and monthly bars (the in-progress bar counts):

- **Cycle** (the workbook's "D", series DAS/DAL): 5-bar SMA minus 15-bar SMA of the close.
- **Trend** (the workbook's "T", series TPL): the Coppock curve, a 10-bar weighted average of (14-bar ROC + 11-bar ROC).

Each is in one of four quadrants — Q1 below zero and rising, Q2 above zero and rising, Q3 above zero and falling, Q4 below zero and falling. The header code is Q-CC-NN: quadrant, bars spent in that quadrant (01 = it just started), bars spent on that side of zero. **Quadrant Balances** are the percentage of an index's members in each quadrant, per oscillator and bar size, plus Q1+Q2 (the share rising).

**Verification.** The formulas were recovered by fitting the 18 header codes in the workbook (S&P 500 and Nasdaq-100; daily/weekly/monthly; 2026-08-21 and 2026-11-20). Trend = standard Coppock matched 6 of 6 at once. Cycle = SMA5 − SMA15 was the only one of 25,710 candidate oscillators to match all 12. The member balances, recomputed from ~499 current S&P members as of the workbook's breadth date (Nov 19), match all 24 printed values within 0.4pp.

**Reading at the Nov 20 close.**

| | S&P 500 cycle | S&P 500 trend | Nasdaq-100 cycle | Nasdaq-100 trend |
|---|---|---|---|---|
| daily | 4-05-25 | 4-05-22 | 4-03-28 | 4-05-26 |
| weekly | 4-03-03 | 4-01-01 | 4-03-03 | 4-02-02 |
| monthly | 3-03-43 | 3-04-40 | 3-02-43 | 3-05-41 |

S&P members in Q4 (declining), Nov 19 → Nov 20: daily cycle 58% → 77%, daily trend 31% → 41%, weekly cycle 23% → 28%, weekly trend 33% → 37%, monthly 19% → 21% and 17% → 18%.

**What the stage count has meant (S&P 500, weekly bars, 1987-2006 / 2007-2026).** Baseline any week: next 4 weeks +0.7% / +0.8%, next 13 weeks +2.3% / +2.5%.

| Weekly decline (Q4), by weeks in it | Cycle: next 4w | Cycle: next 13w | Trend: next 4w | Trend: next 13w |
|---|---|---|---|---|
| 01 | +1.0% / −0.3% | +1.6% / +2.4% | +0.2% / −0.2% | +1.0% / +1.2% |
| 02 | +0.9% / −0.5% | +2.0% / +2.6% | −0.5% / +3.4% | +1.3% / +4.5% |
| 03 | +1.3% / +1.1% | +2.8% / +4.4% | −0.9% / +3.6% | +1.4% / +5.6% |
| 04-05 | +0.4% / +2.4% | +3.7% / +4.5% | +1.0% / +2.6% | +5.3% / +4.0% |
| 06-08 | +3.5% / +4.8% | +5.7% / +9.6% | +2.9% / +2.3% | +5.6% / +2.5% |

A weekly cycle decline lasts a median 3 weeks (90th percentile 7); a weekly trend decline a median 5 (90th percentile 9). When the weekly trend first turns down while the monthly oscillators are still positive (45 episodes since 1986), it then stays below zero a median 12 weeks, the next 4 weeks average +0.6%, the next 13 weeks +3.3% (70% positive), with an average further low of −5.6%.

**The monthly state is the discriminator.** Weeks with weekly cycle and trend both in Q4:

| | n (old / modern) | next 4w | next 13w | up at 13w | worst 13w |
|---|---|---|---|---|---|
| both monthly oscillators above zero | 65 / 68 | +1.5% / +2.7% | +4.6% / +7.0% | 80% / 81% | −10% / −10% |
| a monthly oscillator below zero | 33 / 21 | −1.1% / +3.7% | −0.8% / +1.1% | 61% / 52% | −21% / −30% |

**How this corrects the Nov 20 briefing.** That briefing leaned on short-horizon bounce statistics and the old snapshot's "48% in the crash phase" and called the setup capitulation. The real tool says something more specific: on the weekly scale the decline is young (trend week 1, cycle week 3), which is the stage with the weakest forward month in both eras; the monthly oscillators are still above zero (43 and 40 months) but have been falling for 3-4 months, which is the condition under which weekly declines have historically resolved higher over the following quarter. Both statements hold: an oversold bounce is likely, and the weekly down-leg is not statistically mature.

**Status.** Informational dashboard only — same standing as the shadow classifier and fragility shadow. Logged weekly to `paper/trend_cycle.csv` and reported in the Saturday briefing. The August proxy (`sp500_balance` in the ledger) keeps being logged for continuity but is superseded for interpretation. Open items: Nasdaq-100 and sector member balances (need constituent lists); a history of member balances (needs point-in-time constituents to avoid survivorship); testing whether stage counts improve the swing account's entries (entry 79) — the obvious next experiment, since "skip week 01-02 of a weekly decline" is exactly the kind of filter that account lacks.

## Quadrant Balances as an in/out flag, and how it ties to the regime switch (2026-11-21, entry 85)

User request: name the tool Quadrant Balances, run it daily, make it one of the main in/out flags, find the best way to tie it to the regime classifier, and test it on the present. Thesis offered: a monthly washout is a generational buying opportunity. Code: `research/trend_cycle/{data,signals,study_integration,study_integration2}.py`; flag logic in `src/portfolio/trend_cycle.py` (`market_flag`).

**Data.** S&P 500 index codes on monthly bars back to 1986 (exact). Member balances from the monthly closes of today's 503 constituents (201 with data in 1986, 396 by 2007): survivorship-biased, so past washouts are understated if anything.

**The washout thesis.** Baseline S&P, any month: next 12 months +9.7% / +10.1% (1987-2006 / 2007-2026).

| members in a monthly cycle decline (Q4) | n | next 6m | next 12m | next 24m | 12m positive |
|---|---|---|---|---|---|
| under 10% | 72 / 93 | +5.3% / +5.4% | +9.8% / +10.2% | +26.6% / +17.6% | 86% / 81% |
| 30-40% | 13 / 16 | +3.7% / +7.9% | +7.4% / +13.7% | +25.3% / +32.0% | 69% / 88% |
| 40-50% | 13 / 12 | +10.3% / −3.3% | +13.4% / −1.2% | +14.4% / +21.7% | 69% / 67% |
| **50% or more** | 7 / 13 | **+9.5% / +8.8%** | **+17.5% / +21.4%** | **+33.0% / +39.2%** | 100% / 92% |

True in both eras at the extreme. The zone just below it is treacherous in the modern era because 2008 passed through it on the way down. Episodes where the member trend-Q4 share first reached 45%: April 1988 (+18.5% next 12 months), January 2003 (+32.2%), June 2008 (−28.2%, further low −42.6%, the share then rose to 89%), September 2022 (+19.6%, +86.5% over 36 months). Three generational entries and one that was nine months early.

**Tie-in rules tested** (each overrides the classifier's growth dial at the monthly stamp; the unchanged matrix resolves the book). CAGR change vs v9, modern / pre-2007:

| rule | CONS | MOD | AGG | VAGG | drawdown effect |
|---|---|---|---|---|---|
| QB-out (both monthly readings below zero → growth off) | −0.2 / −0.1 | −0.5 / +0.1 | −1.2 / −1.3 | −2.0 / −2.0 | none |
| QB-only dial (growth = monthly trend above zero) | +0.3 / −0.1 | 0.0 / −0.5 | +1.7 / −3.2 | +2.7 / −5.9 | much worse |
| Full stay-in (growth off but both monthly above zero → stay on) | +0.9 / +0.5 | +1.5 / +0.9 | +5.0 / +2.4 | +8.0 / +2.3 | modern AGG −33→−52% |
| Washout-buy (≥50% members in monthly Q4) | +0.1 / +0.1 | +0.1 / +0.4 | −1.6 / +1.3 | −2.9 / +3.2 | modern AGG −33→−51% |
| Washout + turn (washout in last 6m and index cycle rising) | −0.2 / −0.2 | −0.2 / −0.1 | +1.1 / 0.0 | +1.7 / +0.1 | ≈ none |
| Turn-buy (index monthly cycle Q1) | −0.1 / −0.4 | 0.0 / −2.4 | +1.9 / −6.3 | +2.8 / −9.9 | era flip |
| Early-out (trend falling, ≥30% members trend Q4) | −0.2 / +0.6 | −0.5 / +0.5 | −2.2 / +0.1 | −3.3 / +0.4 | era flip |
| **Partial stay-in 25%** | **+0.3 / +0.1** | **+0.4 / +0.3** | **+1.6 / +0.7** | **+2.9 / +0.9** | **modern −1pp; pre-2007 equal or better** |
| Partial stay-in 50% | +0.5 / +0.3 | +0.8 / +0.5 | +3.0 / +1.4 | +5.2 / +1.5 | modern AGG −33→−38% |

**The finding that matters.** Months when the classifier had growth OFF, split by the monthly quadrant-balance state at that month-end:

| | n (modern / old) | S&P next month | positive | AGG as held | AGG if kept growth-on | worst month if kept on |
|---|---|---|---|---|---|---|
| both monthly readings above zero | 20 / 19 | **+3.2% / +1.7%** | 70% / 74% | +2.9% / +1.6% | +7.8% / +4.2% | −20.0% / −7.3% |
| a monthly reading below zero | 29 / 37 | −0.4% / −0.1% | 55% / 54% | +2.1% / +1.0% | +0.7% / −2.2% | −32.4% / −47.4% |

The classifier's exits are whipsaws more often than not while the monthly quadrant balances are intact, and are real once they break — in both eras. Acting on that fully costs tail risk (March 2020 began with the monthly readings intact). A 25% stay-in keeps most of the benefit per unit of added risk: CAGR and Sortino improve in all eight tier-era cells (modern Sortino CONS 1.54→1.59, MOD 1.65→1.69, AGG 1.35→1.43, VAGG 1.14→1.24), max drawdown is equal or better pre-2007 and 1pp worse in each modern tier. Under the house rule (all metrics, both eras) it is a near miss, so it is a CANDIDATE, not adopted.

**The flag** (computed on every run, logged in `paper/trend_cycle.csv`): WASHOUT (≥50% of members in a monthly cycle decline), BROKEN (both index monthly readings below zero), DETERIORATING (one below), INTACT (both above), qualified by the weekly stage — decline EARLY (weeks 1-3), decline MATURE (week 4+), or none (entry 84) — and compared with the classifier's growth dial.

**Tested on the present (close of 2026-11-20).**

| bars | S&P cycle | S&P trend | members declining (cycle / trend) | members rising |
|---|---|---|---|---|
| daily | 4-05-25 | 4-05-22 | 77% / 41% | 6% / 16% |
| weekly | 4-03-03 | 4-01-01 | 28% / 37% | 53% / 38% |
| monthly | 3-03-43 | 3-04-40 | 21% / 18% | 45% / 40% |

Flag: INTACT, weekly decline EARLY. The daily is washed out, the weekly decline is young, and the monthly is nowhere near a washout — 21% against a 50% line, around the 70th percentile of its own history. On the user's own thesis this is not yet the generational entry; if something larger is under way, the monthly has a long way to deteriorate first. The classifier is provisionally DEFLATION for December while the flag is INTACT: the disagreement state above. Candidate December AGG book (75% defensive + 25% growth-on): QLD 25, GDX 22.5, TLT 18.75, TMF 11.25, QQQ 11.25, SCO 5.6, SHY 5.6, against the model's TLT 25 / TMF 15 / GDX 30 / QQQ 15 / SCO 7.5 / SHY 7.5.

**Limits.** The monthly readings are slow: the monthly cycle would need the S&P near 5,500 at December's close (−20%) to turn negative, and the monthly trend far lower, so INTACT will persist through any ordinary correction and through the first months of a real bear market. Sixteen variants were tried; the partial stay-in is a refinement chosen after seeing the full stay-in's drawdown. Member history is survivorship-biased.


## The November 2026 sell-off: was it visible beforehand? (2026-11-21, entry 86)

User question: looking only at Quadrant Balances, was the sell-off indicated, and did any of our models predict it. Code: `research/trend_cycle/study_selloff.py` (day-by-day reconstruction, ex-ante, partial week and month included as the tool does) and `study_signals2.py` (crash-week census and base rates, S&P 500 1950-2026).

**What happened.** The S&P 500 made its closing high of 7,819 on 6 October inside a flat ten-week range (7,550-7,820), wobbled on 5 November (−4.4% in a day), recovered to 3.3% under the high by Friday 13 November, then fell 8.6% in the week of 16-20 November.

**What Quadrant Balances showed, in order.**

| when | reading |
|---|---|
| from July | weekly trend falling above zero (Q3); the 6 Oct index high came on a lower trend reading |
| September | monthly cycle and monthly trend both rolling over above zero (Q3 and Q3), and staying there |
| 6 Oct, the high | 48% of S&P members in a weekly cycle decline, only 33% rising; under half of members rising on the monthly |
| mid-Oct to 13 Nov | members HEALED while the index went sideways: weekly cycle rising 33% → 74%, weekly Q4 share 48% → 18% |
| 2 Nov | index weekly cycle crosses below zero (Q4) |
| 12-13 Nov | 6% of members in a daily cycle decline, the lowest of the autumn |
| 16 Nov | index weekly trend crosses below zero |
| flag | INTACT on every day |

So the tool showed a slow multi-month roll-over, and a member divergence at the high that had repaired itself before the break. It did not show an alarm.

**Do those states predict anything? Base rates (1950-86 / 1987-2006 / 2007-2026).**

| state on a Friday | weeks | next 4 weeks | chance of a 5%+ fall next week | chance of a 7% low within 4 weeks |
|---|---|---|---|---|
| any week | 1906 / 1044 / 1038 | +0.6 / +0.7 / +0.8% | 0.8 / 1.3 / 2.5% | 4.2 / 5.3 / 7.4% |
| weekly trend rolling over (Q3) | 599 / 379 / 397 | +1.0 / +0.9 / +0.7% | 0.3 / 1.1 / 1.8% | 2.0 / 3.4 / 4.0% |
| weekly cycle Q4 with weekly trend Q3 (13 Nov) | 124 / 76 / 62 | +1.4 / +1.7 / +0.5% | 0.0 / 3.9 / 3.2% | 0.8 / 5.3 / 6.5% |
| monthly both rolling over | 399 / 267 / 225 | −0.1 / +1.4 / +0.8% | 1.0 / 0.4 / 3.1% | 5.3 / 3.4 / 8.4% |
| all of the above together | 21 / 4 / 8 | +1.9% / thin / −1.9% | 0.0% / thin / 12.5% | 0.0% / thin / 25.0% |

The 13 November state is the same weekly state as the Friday before the 1987 crash (cycle Q4 week 1, trend Q3 week 6, monthly intact) and the week of 13 March 2020. It roughly triples the weekly crash odds in the two house eras and does nothing before 1987; even at its worst it is a 96% chance of an ordinary week. The full combination looks dangerous only in the modern era on eight weeks.

**The crash-week census.** 36 weekly falls of 6% or more since 1950. 56% started from weekly trend Q4 (17% of all weeks) and 58% from weekly cycle Q4 (19%): crash weeks come out of markets that are already declining. Only 8 of 36 began within 5% of a 52-week high — 1978, 1979, 1986, 1989, April 2000, May 2010, February 2020 and this one. Half began with the monthly intact.

**What the other models said.**

| model | last reading before the break | verdict |
|---|---|---|
| Regime classifier | 31 Oct: SPY 4.6% above its line, DBC 16.9% above; 13 Nov: 3.4% / 3.4% | clean, Reflation |
| Shadow classifier | Reflation | clean |
| Sector breadth | 67% above their 10-month averages on 1 Nov and 13 Nov | clean |
| Fragility shadow (entry 70) | FRAGILE on 5, 6, 10 and 16 Nov; 13 Nov missed the 3% band by 0.02 points | **flagged** |
| Quadrant Balances flag | INTACT; weekly cycle Q4 from 2 Nov | deteriorating, not flagged |
| Swing account | blocked on 16 Nov by the fragile gate, bought SPY on 17 Nov | caught in it |

The fragile state is the only thing that fired. On daily closes a 7% low within 10 days follows 1.2 / 5.2 / 6.5% of fragile days against 0.7 / 1.4 / 1.3% of days when the index is more than 3% above its 200-day average, so in the two house eras it marks four to five times the crash risk. Its average forward return is still positive (+0.6 to +3.3% over 21 days), which is why de-levering on it failed the two-era test (entry 70) and why it runs as a shadow. Days BELOW the 200-day average are riskier still (12.6% in the modern era).

**Verdict.** Nothing predicted the sell-off. Two risk states were up — the fragile state, and the weekly cycle below zero under a rolling-over monthly — and neither has a base rate that would justify acting on it. Consistent with every earlier attempt at early warning (entries 32-33, 41-45, 47, 70).

## Quadrant Balances: when it says buy and when it says sell (2026-11-21, entry 87)

User request: find when the tool indicates a buy and a sell, on two levels — the monthly for multi-year bottoms and tops, the weekly for intra-year ones. Code: `research/trend_cycle/study_signals.py`, `study_signals2.py`, `study_integration3.py`. S&P 500 index states (exact) on completed weekly and monthly bars, 1950-2026. Eras: 1950-86 (extra, price only), 1987-2006, 2007-2026. Rules use total return from 1987 (index fund, 3-month bills when out).

**Monthly transitions, next 12 months** (baseline +8.4 / +9.7 / +10.2%, higher 69 / 79 / 79% of the time):

| signal | n | next 12 months | higher | average worst point |
|---|---|---|---|---|
| BUY trend turns up from below zero (Q4→Q1) | 11 / 5 / 3 | +21.7% / +10.3% / thin (all 3 up) | 91% / 80% | −2.1% / −7.8% |
| BUY cycle crosses back above zero | 11 / 4 / 7 | +15.2% / +16.0% / +13.5% | 91% / 100% / 86% | −3.4% / −1.7% / −4.3% |
| SELL trend rolls over above zero (→Q3) | 24 / 23 / 20 | +5.9% / +11.2% / +8.3% | 58% / 83% / 72% | −7.5% / −3.6% / −8.6% |
| SELL both rolling over, first month | 33 / 23 / 21 | +5.3% / +8.2% / +4.7% | 61% / 78% / 58% | −5.7% / −4.8% / −7.8% |
| SELL trend crosses below zero (→Q4) | 10 / 3 / 3 | +7.3% / thin / thin (3 months: −2.8%) | 70% | −11.3% |
| SELL both below zero and falling, first month | 15 / 4 / 5 | +15.3% / −4.4% / +3.0% (6 months: +1.3 / +2.9 / −6.4%) | 87% / 25% / 60% | −10.5% / −13.8% / −16.9% |

**Against the 13 bear markets (20% moves on daily closes).** Monthly trend turning up caught 11 of 13 lows, a median 4 months and 18% after the low (missed: the interim low of November 2008, whose final low in March 2009 was caught, and March 2020, which was too fast; the 1987 low was caught nine months late). Monthly cycle back above zero caught 11, a median 8 months and 28% after. On the way down: a roll-over into Q3 appears within 2 months of 8-10 of the 13 tops — and 60-85 other times. The trend crossing below zero caught 8 tops a median 9.5 months and 12% late.

Monthly trend turns up: 1954-01, 1957-07, 1958-04, 1960-12, 1963-01, 1967-01, 1970-08, 1975-01, 1978-04, 1982-08, 1984-12, 1988-09, 1991-02, 2001-12, 2002-11, 2003-04, 2009-05, 2016-05, 2023-03. Monthly trend crosses below zero: 1953-09, 1957-05, 1960-07, 1962-07, 1966-08, 1969-10, 1973-09, 1977-08, 1982-01, 1984-09, 1988-04, 1990-11, 2001-02, 2008-05, 2016-02, 2022-09.

**As rules on the index** (CAGR / worst drawdown / Sharpe):

| rule | 1950-86 | 1987-2006 | 2007-2026 | switches a year |
|---|---|---|---|---|
| buy and hold | +6.6% / −46% / 0.53 | +11.6% / −45% / 0.82 | +9.0% / −52% / 0.64 | 0 |
| 10-month average (the classifier's rule) | +6.4% / −18% / 0.66 | +10.0% / −24% / 0.89 | +8.0% / −22% / 0.79 | 1.4 |
| **out only while monthly trend is Q4** | +7.2% / −23% / 0.65 | +11.4% / −31% / 0.87 | +10.4% / −25% / 0.81 | 0.4 |
| out on Q4, or on trend Q3 with cycle Q4 | +7.4% / −19% / 0.71 | +10.9% / −30% / 0.85 | +10.4% / −20% / 0.85 | 0.7 |
| in only while trend rising | +6.1% / −15% / 0.73 | +6.6% / −24% / 0.73 | +6.2% / −20% / 0.73 | 2.3 |
| in only while trend above zero | +4.4% / −23% / 0.46 | +11.3% / −30% / 0.89 | +9.0% / −28% / 0.73 | 0.3 |

Of the 19 round trips of the first rule, 7 bought back lower (1957, 1970, 1975, 1982, 2001, 2002, 2009) and 12 paid up, including four exits at the exact low month (1988, 1990, 2016, 2022). The rule earns its keep in the long bears and gives some back in the fast ones.

**Weekly.** No weekly transition shows an edge in all three eras, in either direction. After a weekly trend cross below zero the next 26 weeks returned +3.0 / +6.7 / +6.5% (base 4.3 / 4.6 / 5.0). All 17 weekly long/flat rules lose to buy-and-hold on return; "in while weekly trend rising" earns +3.1 / +5.7 / +5.1%. Skipping only the first three weeks of a weekly decline helps the modern era (+2.6pp) and costs the one before (−0.9pp).

**The weekly only works through the monthly.** Monthly state = last completed month; intact = both readings above zero, broken = both below.

| weekly event | monthly intact: next 13w / 26w | monthly broken: next 13w |
|---|---|---|
| weekly cycle turns up while weekly trend decline is in week 4+ | +3.8 / +4.8 / +4.9% and +7.2 / +7.2 / +6.6% (n 15 / 12 / 13; higher at 13w 60 / 75 / 85%) | +0.4% / thin / thin |
| same turn in weeks 1-3 of the decline | −0.3% / thin / +1.0% | thin |
| every week of a weekly trend decline, week 4+ | +1.8 / +5.6 / +7.1% | +2.0 / +2.6 / −13.0% |
| weekly trend turns up from below zero | −1.7 / +2.9 / +2.8% | +2.3 / −5.0% / thin |

**Member balances (monthly, today's constituents, 1987-2006 / 2007-2026).** Washout (50%+ in a monthly cycle decline): +17.5 / +21.4% over 12 months. Every member-based sell tested (45%+ rolling over, index trend up on under 45% of members, members rising under 30% with the index trend above zero, index near a high with 40%+ rolling over) is followed by returns at or above baseline in at least one era.

**In the matrix (CAGR change vs v9, modern / pre-2007; AGG drawdown).**

| use of the monthly signal | CONS | MOD | AGG | VAGG | AGG drawdown |
|---|---|---|---|---|---|
| replaces the classifier (growth on unless trend Q4) | +0.9 / 0.0 | +1.6 / −1.0 | +6.3 / −3.0 | +9.5 / −6.8 | −33→−52% / −43→−64% |
| replaces it, earlier exit | +1.0 / +0.4 | +1.8 / +0.4 | +6.5 / +0.6 | +9.8 / −2.4 | −52% / −44% |
| classifier, but stay on unless trend Q4 | +0.8 / −0.1 | +1.3 / −1.3 | +5.3 / −3.0 | +8.1 / −6.4 | −52% / −64% |
| classifier AND not trend Q4 (second veto) | +0.1 / +0.1 | +0.3 / +0.3 | +1.0 / 0.0 | +1.2 / −0.5 | −33% / −41% |

The index-level result does not carry into the leveraged books: the monthly signal exits too late for them. The second veto changes five months per era and improves all three metrics in five of eight cells. Filed as a near miss on a thin sample; no change.

**The map.**

| level | BUY | SELL |
|---|---|---|
| Monthly (multi-year) | early: monthly trend turns up from below zero. Confirmed: monthly cycle back above zero. Extreme: 50%+ of members in a monthly cycle decline | only one: monthly trend crosses below zero. Late by design. A roll-over above zero is a caution, not a sell |
| Weekly (intra-year) | only with the monthly intact: weekly trend decline in week 4 or later, then the weekly cycle turns up | none. No weekly state marks a top |

**Where this puts 20 November 2026.** Monthly intact but both readings rolling over (caution state, month 3 and 4). No multi-year sell: the monthly trend turns negative only if the S&P is near 5,480 at the January close, 6,020 at the February close or 6,680 at the April close; the monthly cycle goes negative at about 6,200 by the December close. Weekly: trend decline in week 1, cycle in week 3. The intra-year buy is not armed before the week ending 11 December (week 4), and then needs the weekly cycle to turn up.

**Limits.** 13 bear markets and 19 monthly buy signals in 76 years; the modern era has three monthly buys. The 1950-86 era has no dividends or reliable bill yields before 1960. Signals were defined before looking at the forward tables, but the "week 4+" threshold comes from entry 84's stage table on the same data. Member history is survivorship-biased.


## Intraday forex technical rules, pre-registered (2026-11-26, entry 88)

User request: build the test harness from the intraday forex report and run its plan. Code: `research/fx_intraday/` (data, costs, engine, rules, stats, registry, run). Pre-registration `research/fx_intraday/PREREGISTRATION.md` was committed (206cfdc) before any backtest. Every evaluated variant is in `research/fx_intraday/trials.csv`; results in `research/fx_intraday/results/`.

**Data.** Dukascopy, the report's first choice, closed its free feed (HTTP 429, now a paid AWS bucket) as of 2026-11-26. FXCM's public candle repository serves minute bid and ask candles for 2012 to 2026 week 46 with no key, so that is the source. It is one dealer's quotes: 2012-2022 have crossed quotes (ask below bid) on up to 7% of minutes, almost none from 2023, which the cost model absorbs by taking max(feed spread, base spread). The hold-out window has holes (14 Dec 2024 - 11 Jan 2025, 20-27 Jun and 11-27 Jul 2025, 1 May - 9 Aug 2026); it was never opened.

**Costs.** OANDA US spread-only, 1.4 pips on EUR/USD, about 1.22 bp per round trip for time-exit trades and up to 1.5 bp with stop slippage. CME Micro EUR/USD reference (stress 1.15) gives the same verdicts.

**Results, EUR/USD development sample 2012-01 to 2024-11, base cost.**

| trial | trades | gross bp | net bp | t | 2012-17 net | 2018-24 net |
|---|---|---|---|---|---|---|
| drift A: short 08:00-14:15 Berlin | 3,267 | +2.16 | +0.94 | 1.85 | +2.06 | -0.04 |
| drift B: long 16:00 London to 16:45 New York | 3,267 | +1.44 | +0.22 | 0.56 | +1.36 | -0.78 |
| drift A+B | 6,534 | +1.80 | +0.58 | 1.80 | +1.71 | -0.41 |
| best mean reversion (k 2.0, stop 2 ATR, 8 h) | 5,218 | -0.01 | -1.30 | -4.24 | -1.44 | -1.19 |
| worst mean reversion (k 2.5, stop 2 ATR, 4 h) | 2,962 | -0.48 | -1.76 | -4.64 | | |
| best round-number variant | 762 | +0.20 | -1.09 | -1.31 | -1.36 | -0.85 |
| London breakout (calibration) | 3,151 | -0.16 | -1.65 | -3.89 | -1.27 | -1.99 |

Drift A by year, gross bp per trade: 2012 4.6, 2013 2.0, 2014 4.0, 2015 4.8, 2016 2.1, 2017 2.0, 2018 2.4, 2019 1.7, 2020 0.7, 2021 1.3, 2022 1.2, 2023 1.0, 2024 0.05.

**Gates.** No family passed. Drift A failed the cost ratio (1.77 against 2), the two-window test (negative 2018-24) and the snooping test (SPA p = 0.095 across all 20 trials; StepM keeps none; t 1.85 against 3). It did beat the random-entry null (p = 0.005), so the time-of-day pattern itself is real, not noise. Mean reversion failed every gate it could: gross is zero in all eight variants and the walk-forward record is -1.35 bp a trade (t -3.2). The round-number filter's true grid (-1.09 bp) lost to shifted grids at 27 and 37 pips (-0.55 and -0.37 bp) and had under 1,000 trades. The breakout lost to random entries (p = 0.79): the calibration reproduced the known weak result.

**Reading.** This is the null the report expected, now measured on data the literature had not used (2020-2024) with retail costs. The one real effect, the dollar strengthening into the European fixes, was worth about 4-5 bp a trade in 2012-15 and has faded to nothing by 2024 — the same decay Krohn, Mueller and Whelan (2024) describe, extended five years. At 1.2-1.5 bp a round trip, retail intraday rules on EUR/USD need a gross edge that none of these ideas has had since about 2019.

**What the harness is good for now.** It runs a new idea through the same gates in minutes. Any next idea must be written into the pre-registration first and counted in `trials.csv`; the hold-out stays locked until something passes. The only lever the evidence points to is execution cost (resting limit orders, or the futures path), which would be a new, separately registered test, not a re-run of these.


## The swing accounts at a $1,000 balance (2026-11-26, entry 89)

User plan: fund a separate IBKR account with $1,000 to test strategies, aiming for $50, then $100, then $200 a month in gains. IBKR still applies the $25,000 pattern-day-trader rule to this user (FINRA removed it on 4 June 2026, but brokers may keep it until 20 October 2027). Both swing designs enter at a close and exit at a later close, so they never make a day trade. Code: `research/swing/study_small_account.py`; table in `research/swing/small_account_results.csv`.

**Costs at this size.** IBKR Pro charges a $0.35 minimum per order. On two $500 slots that is 7 bp per side, plus 1-2 bp of spread and fees: 8-9 bp per side, against the 5 bp assumed in tests 79 and 82. At $5,000 it falls to about 3.4 bp.

| design, 1999-2026 | CAGR | max drawdown | average month on $1,000 | worst month on $1,000 | 12-month return, 1-in-20 worst |
|---|---|---|---|---|---|
| test 79, 1x, entry at the close | +5.9% | -14% | +$5 | -$88 | -5.0% |
| test 79, 2x | +10.2% | -27% | +$9 | -$178 | -10.3% |
| test 79, 3x | +14.4% | -38% | +$12 | -$270 | -17.0% |
| test 79, 1x, entry at next open | +4.5% | -13% | +$4 | -$85 | -4.8% |
| test 79, 3x, entry at next open | +10.2% | -42% | +$9 | -$265 | -17.4% |
| test 82, 1x | +7.6% | -14% | +$6 | -$75 | -3.9% |
| SPY buy and hold | +8.3% | -55% | +$8 | -$165 | -22.4% |

**What each milestone needs.** Expected monthly gain is balance x CAGR / 12.

| design | $50 a month | $100 a month | $200 a month |
|---|---|---|---|
| test 79, 1x | $10,250 | $20,500 | $41,000 |
| test 79, 2x | $5,870 | $11,740 | $23,480 |
| test 79, 3x | $4,150 | $8,310 | $16,620 |
| test 82, 1x | $7,940 | $15,880 | $31,750 |

**How long from $1,000, by monthly contribution** (years to $50 / $100 / $200 a month, at the historical CAGR).

| design | nothing added | +$100 a month | +$250 a month | +$500 a month |
|---|---|---|---|---|
| test 79, 1x | 41 / never / never | 6.3 / 11.4 / 18.5 | 2.9 / 5.7 / 10.1 | 1.6 / 3.1 / 5.8 |
| test 79, 2x | 19 / 26 / 33 | 3.4 / 6.3 / 10.5 | 1.6 / 3.2 / 5.8 | 0.8 / 1.8 / 3.3 |
| test 79, 3x | 11 / 16 / 21 | 2.2 / 4.4 / 7.4 | 1.1 / 2.2 / 4.1 | 0.6 / 1.2 / 2.3 |
| test 82, 1x | 29 / 38 / 48 | 4.8 / 8.8 / 14.3 | 2.2 / 4.3 / 7.8 | 1.2 / 2.4 / 4.5 |

**Lumpiness.** The account holds a position in about two-thirds of months and is flat otherwise. At $10,000, a calendar month cleared $50 in 42% (1x) to 47% (3x) of months; at $25,000, $200 in 33% to 44%. A milestone should be read as a 12-month average, never as a monthly target.

**Reading.** At $1,000 the strategy is a measurement exercise: it will make single-digit dollars in an average month and can lose $90 to $270 in a bad one. The milestones are reached by balance far more than by strategy choice; contributions dominate leverage. The paper record so far (two trades from 17 to 23 November) is too short to say anything.

## Options on the 3x funds instead of the funds (2026-11-26, entry 90)

Question: would options on UPRO or TQQQ do better than holding the fund for the test-79 swing trades? Code: `research/swing/study_options_3x.py`. Model only, no historical option chains: Black-Scholes at 30 days to expiry on the actual fund price paths, implied vol of 3 x 0.90 x VIX (UPRO) or VXN (TQQQ) with skew, a half-spread of 1% (TQQQ) or 2.5% (UPRO) and $0.65 a contract. 295 trades from 2011, model IV at entry 53% (UPRO) and 60% (TQQQ).

| per trade, return on money at risk | mean | median | win rate | 2011-16 | 2017-26 |
|---|---|---|---|---|---|
| 3x fund | +1.4% | +2.4% | 70% | +0.9% | +1.7% |
| long ATM call | -7.2% | -1.3% | 49% | -25.0% | +4.1% |
| long 0.90 ITM call | -6.9% | -0.8% | 48% | -14.8% | -1.9% |
| call debit spread 1.00/1.05 | -31.4% | -24.8% | 32% | -69.9% | -6.8% |
| call debit spread 1.00/1.10 | -22.3% | -18.7% | 40% | -55.4% | -1.1% |

| account, $1,000 start + $150 a month, 2011-2026 ($29,500 deposited) | end balance | worst drop |
|---|---|---|
| 3x fund, half the account per slot | $86,654 | -27% |
| long ATM call, 10% a trade | $30,116 | -31% |
| long ATM call, 25% a trade | $67,559 | -72% |
| long ITM call, 10% a trade | $16,692 | -19% |
| call debit spread 1.00/1.10, 10% a trade | $19,828 | -40% |
| call debit spread 1.00/1.10, 25% a trade | $30,691 | -86% |

**Reading.** The swing edge is 1-2% over three to five days. A 30-day option on a 3x fund costs 50-60% implied vol, so the time decay and spread consume the edge, and the strikes are rarely far enough in the money to act like the fund. Per contract at risk: UPRO ATM about $152, TQQQ ATM about $49, so the small account can trade them, but nothing in the model says it should. Put credit spreads are left out: they need a margin account, and the model is unreliable for them at extreme volatility. The live plan stays with the 3x funds themselves.

## Weekly options on the 3x funds (2026-11-26, entry 91)

Follow-up to entry 90: a few-day trade does not need a 30-day option. Code: `research/swing/study_options_3x_weekly.py`; table in `research/swing/options_3x_weekly_results.csv`. Same 295 trades and option model. Expiry is the first Friday at least 3, 7 or 14 days after entry; if the signal has not exited by then, the option is sold at that Friday's close. Trades are held a median 5 calendar days, the longest 14.

| long ATM call | days to expiry, median | per trade | round-trip spread, share of premium | first day's decay | cost per contract, UPRO / TQQQ | account at 10% a trade | account at 25% a trade |
|---|---|---|---|---|---|---|---|
| Friday 3+ days out | 7 | -14.5% | 12% | 6.4% | $73 / $19 | $27,973 (-52%) | $27,783 (-86%) |
| Friday 7+ days out | 9 | -15.0% | 9% | 5.3% | $87 / $28 | $23,325 (-50%) | $25,794 (-85%) |
| Friday 14+ days out | 16 | -10.7% | 7% | 3.0% | $113 / $37 | $29,459 (-41%) | $55,894 (-81%) |
| 30 days | 30 | -7.2% | 6% | 1.6% | $152 / $49 | $30,116 (-31%) | $67,559 (-72%) |
| 3x fund itself | | +1.4% | | | | $86,654 (-27%) | |

Accounts start at $1,000 with $150 a month added ($29,500 deposited); the worst drop is in brackets.

**Reading.** A cheaper, nearer option buys more leverage per dollar but loses value faster and pays a larger share of its price in spread. A one-week ATM call needs the fund to rise about 2% before it breaks even; the average swing trade rises 1.4%. In-the-money calls and debit spreads cut the decay but keep the spread, and none beat the fund. With the spread doubled, every weekly variant ends between $3,000 and $20,000. The live plan stays with the 3x funds.
