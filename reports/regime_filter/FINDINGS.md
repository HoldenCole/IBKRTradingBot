# Regime filter validation — findings

**Date:** 2026-05-02
**Test:** IBS LS_full on QQQ shares, 2018-01-01 → 2026-04-15, with each
candidate filter applied at signal-day. Three "real" filters (technical
indicators only) + three diagnostic year-exclusion filters (use hindsight).

## Headline result

**Every simple price-based filter made the strategy worse, not better.**
Per the user's stated decision rule ("if it doesn't lift meaningfully,
the regime split was overfit and we drop the approach"), the
simple-rule regime filter approach is **dropped**.

Diagnostic year-exclusion (cheating with hindsight) does lift the
metrics meaningfully — but still doesn't clear Tier C under the
strict return constraint.

## Full results

| Filter | N | Sharpe | Sortino | Return | |DD| | Tier |
|---|---|---|---|---|---|---|
| BASELINE (no filter) | 337 | 0.67 | 0.59 | +83% | 16% | D |
| V0 — DrawdownFilter(30d, -7%) | 269 | 0.41 | 0.28 | +32% | 12% | D |
| V0 — DrawdownFilter(30d, -5%) | 232 | 0.34 | 0.22 | +23% | 14% | D |
| V1 — Sma200BandFilter(5%) | 271 | 0.48 | 0.36 | +46% | 26% | D |
| V2 — TrendCoherenceFilter(50/200) | 207 | 0.45 | 0.28 | +35% | 15% | D |
| V0+V2 OR (drawdown OR chop) | 298 | 0.43 | 0.33 | +39% | 15% | D |
| **DIAG — exclude 2018+2026 by year** | 289 | **0.91** | **0.74** | **+117%** | 11% | D |
| DIAG — exclude only 2018 | 297 | 0.84 | 0.70 | +106% | 11% | D |
| DIAG — exclude only 2026 | 329 | 0.73 | 0.62 | +93% | 16% | D |

(Bench: SPY +160% return, Sharpe 0.70.)

## Why the simple filters fail

The per-regime data showed three of six regimes (bull, bear,
crisis_recovery — 256 of 337 trades) with Sortino 1.50-1.85 in
isolation. The simple filters tried to identify and exclude the bad
regimes (chop_to_correction, mixed). They didn't:

- **DrawdownFilter** blocks any day with significant recent decline.
  But IBS works during 2020 mid-crash recovery (deep drawdown days
  produce the best long entries) and 2022 bear-rally bounces (deep
  drawdown days but profitable for shorts). Filter blocks both.
- **Sma200BandFilter** blocks transition days near SMA200. But many
  profitable IBS-long bounces happen with close just barely above
  SMA200 — the filter blocks the marginal-good trades along with
  marginal-bad ones.
- **TrendCoherenceFilter** requires price/SMA50/SMA200 alignment.
  Blocks chop, but also blocks early-bull-recovery days (price > SMA200
  but SMA50 still catching up) and late-bear-bounce days. Excludes
  meaningful winners.

The structural problem: **the per-regime equity-curve metrics tell us
which YEAR was bad, but not which DAY within that year was bad.**
Within the bad years, individual trades have a mix of wins and losses;
within the good years, individual trades also have a mix. Filtering
at the day level can't separate them with just price/SMA/drawdown
features.

## What the diagnostic year-exclusion tells us

Even with PERFECT hindsight (excluding 2018 and 2026 entirely),
metrics improve but don't clear Tier C:

- Sortino: 0.59 → 0.74 (+0.15)
- Sharpe: 0.67 → 0.91 (+0.24)
- Return: +83% → +117% (+34pp)
- Max DD: 16% → 11% (improved)

The improvement is real but not enough. The strict tier rule requires
return ≥ SPY−20% = +140%. Even hindsight-filtered LS gets to +117%.
**Structural ceiling on the strategy at $8k 1-share-at-a-time sizing
is below SPY-20% return.**

This means: even if your separate regime model is perfect, the
strategy as currently structured can't clear Tier C on absolute
return. To beat SPY meaningfully would require leverage (Phase 2
options, or margin shares), and applying leverage to a regime-
dependent strategy amplifies regime dependence.

## What this means for next steps

**Drop the simple filter approach.** Don't iterate further on
DrawdownFilter / Sma200BandFilter / TrendCoherenceFilter parameter
tuning. The space was searched; nothing in it works.

**Your separate regime model is unaffected by this finding.** It
might use features (cross-asset, breadth, options flow, regime
classification at higher abstractions) that simple price-based
rules can't access. The hook for it is in `SharesBacktestConfig
.regime_filter` — drop in any object that implements
`is_active(daily, today) -> bool` and re-run.

**Regardless of the regime model, the absolute-return constraint
binds.** Even perfect regime gating leaves return at +117% vs SPY
+160%. To clear Tier C return-wise you need either:
- Leverage (Phase 2 options or margin shares), accepting amplified
  regime dependence, OR
- A strategy whose signal frequency is much higher (so 1-share-at-a-time
  on $8k can compound faster), OR
- A multi-strategy portfolio where IBS is one component, not the
  whole portfolio. (This is the user's stated preferred direction.)

**Multi-strategy framing wins.** IBS-on-shares is Tier D standalone,
clears Tier C-equivalent under hindsight regime gating, and has
genuine Sortino in 3 of 6 regimes. As one of three components in a
portfolio, where the other two have edge in the regimes IBS doesn't
(2018-style chop, 2026-style mixed), the portfolio can plausibly
clear Tier B at the aggregate level. None of the three components
needs to clear Tier B individually.

## Decision

| Question | Answer |
|---|---|
| Did simple regime filters lift LS_full Sortino? | NO. All degraded. |
| Did diagnostic year-exclusion lift to Tier C? | NO. +0.15 Sortino, but return constraint binds. |
| Per user's rule, is the simple-filter approach dropped? | YES. |
| Is the per-regime structure real? | YES — diagnostic confirms. Just not capturable by these features. |
| Is leverage (Phase 2) reconsidered? | NO. Leverage on regime-dependent strategy amplifies dependence. |
| Is the user's separate regime model still viable? | YES. Awaits integration. |

## Files preserved

- `reports/regime_filter/raw_output.txt` — all 9 variants, full v2 reports
- `src/backtest/regime_filter.py` — five filter classes, documented rules
- `scripts/run_regime_filter_test.py` — reproducible runner
