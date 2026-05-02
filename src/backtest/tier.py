"""Tier classifier per the v2 validation plan.

Tier A: max DD < 25%, (Sharpe>1.5 OR Sortino>1.5), (return>=SPY OR Sharpe>=SPY+0.8)
Tier B: max DD < 35%, (Sharpe>=1.0 OR Sortino>=1.0), (return>=SPY OR Sharpe>=SPY+0.4)
Tier C: max DD < 35%, (Sharpe>=0.5 OR Sortino>=0.5), return>=SPY-20%
Tier D: anything else.

The Sharpe-or-Sortino rule was added per the user's revision: a strategy
qualifies for a tier if EITHER Sharpe or Sortino clears the numerical
threshold. This rewards strategies with downside-controlled return
profiles whose Sharpe is suppressed by upside volatility.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TierVerdict:
    tier: str          # "A" | "B" | "C" | "D"
    rationale: str     # human-readable explanation


def classify(
    strategy_sharpe: float,
    strategy_max_dd: float,         # negative, e.g. -0.18
    strategy_total_return: float,   # e.g. 1.20 for +120%
    bench_sharpe: float,
    bench_total_return: float,
    strategy_sortino: float = 0.0,  # optional; default 0 makes rule reduce to Sharpe-only
) -> TierVerdict:
    """Apply the v2 tier rules. max_dd is expected as a negative number;
    the absolute-value check uses abs(max_dd). Sharpe OR Sortino qualifies."""
    abs_dd = abs(strategy_max_dd)
    sharpe_lift_vs_bench = strategy_sharpe - bench_sharpe
    sortino_lift_vs_bench = strategy_sortino - bench_sharpe  # bench Sortino not always available; conservative
    risk_ratio = max(strategy_sharpe, strategy_sortino)
    risk_ratio_label = "Sharpe" if strategy_sharpe >= strategy_sortino else "Sortino"

    # Tier A
    if risk_ratio > 1.5 and abs_dd < 0.25:
        if strategy_total_return >= bench_total_return or sharpe_lift_vs_bench >= 0.8:
            return TierVerdict(
                "A",
                f"{risk_ratio_label} {risk_ratio:.2f} > 1.5, |DD| {abs_dd:.0%} < 25%, "
                f"and ({'beats bench return' if strategy_total_return >= bench_total_return else f'Sharpe lift {sharpe_lift_vs_bench:.2f} >= 0.8'})",
            )

    # Tier B
    if risk_ratio >= 1.0 and abs_dd < 0.35:
        if strategy_total_return >= bench_total_return or sharpe_lift_vs_bench >= 0.4:
            return TierVerdict(
                "B",
                f"{risk_ratio_label} {risk_ratio:.2f} in [1.0,1.5), |DD| {abs_dd:.0%} < 35%, "
                f"and ({'beats bench return' if strategy_total_return >= bench_total_return else f'Sharpe lift {sharpe_lift_vs_bench:.2f} >= 0.4'})",
            )

    # Tier C
    if risk_ratio >= 0.5 and abs_dd < 0.35:
        if strategy_total_return >= bench_total_return - 0.20:
            return TierVerdict(
                "C",
                f"{risk_ratio_label} {risk_ratio:.2f} in [0.5,1.0), |DD| {abs_dd:.0%} < 35%, "
                f"return {strategy_total_return:+.0%} within 20pp of bench {bench_total_return:+.0%}",
            )

    # Tier D — explain why
    reasons = []
    if risk_ratio < 0.5:
        reasons.append(f"both Sharpe ({strategy_sharpe:.2f}) and Sortino ({strategy_sortino:.2f}) below 0.5")
    if abs_dd >= 0.35:
        reasons.append(f"|DD| {abs_dd:.0%} >= 35%")
    if strategy_total_return < bench_total_return - 0.20 and risk_ratio < 1.0:
        reasons.append(f"return {strategy_total_return:+.0%} > 20pp below bench")
    if not reasons:
        reasons = ["combined Sharpe/Sortino/DD/return below all upper-tier thresholds"]
    return TierVerdict("D", "; ".join(reasons))
