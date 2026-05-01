"""Tier classifier per the v2 validation plan.

Tier A: Sharpe > 1.5, max DD < 25%, (return >= SPY OR Sharpe >= SPY+0.8)
Tier B: Sharpe 1.0-1.5, max DD < 35%, (return >= SPY OR Sharpe >= SPY+0.4)
Tier C: Sharpe 0.5-1.0, max DD < 35%, return >= SPY-20%
Tier D: anything else.
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
) -> TierVerdict:
    """Apply the v2 tier rules. max_dd is expected as a negative number;
    the absolute-value check uses abs(max_dd)."""
    abs_dd = abs(strategy_max_dd)
    sharpe_lift_vs_bench = strategy_sharpe - bench_sharpe
    return_vs_bench = strategy_total_return - bench_total_return

    # Tier A
    if strategy_sharpe > 1.5 and abs_dd < 0.25:
        if strategy_total_return >= bench_total_return or sharpe_lift_vs_bench >= 0.8:
            return TierVerdict(
                "A",
                f"Sharpe {strategy_sharpe:.2f} > 1.5, |DD| {abs_dd:.0%} < 25%, "
                f"and ({'beats bench return' if strategy_total_return >= bench_total_return else f'Sharpe lift {sharpe_lift_vs_bench:.2f} >= 0.8'})",
            )

    # Tier B
    if 1.0 <= strategy_sharpe and abs_dd < 0.35:
        if strategy_total_return >= bench_total_return or sharpe_lift_vs_bench >= 0.4:
            return TierVerdict(
                "B",
                f"Sharpe {strategy_sharpe:.2f} in [1.0,1.5), |DD| {abs_dd:.0%} < 35%, "
                f"and ({'beats bench return' if strategy_total_return >= bench_total_return else f'Sharpe lift {sharpe_lift_vs_bench:.2f} >= 0.4'})",
            )

    # Tier C
    if 0.5 <= strategy_sharpe and abs_dd < 0.35:
        # "return >= SPY-20%" means within 20 percentage points below the bench
        if strategy_total_return >= bench_total_return - 0.20:
            return TierVerdict(
                "C",
                f"Sharpe {strategy_sharpe:.2f} in [0.5,1.0), |DD| {abs_dd:.0%} < 35%, "
                f"return {strategy_total_return:+.0%} within 20pp of bench {bench_total_return:+.0%}",
            )

    # Tier D — explain why
    reasons = []
    if strategy_sharpe < 0.5:
        reasons.append(f"Sharpe {strategy_sharpe:.2f} < 0.5")
    if abs_dd >= 0.35:
        reasons.append(f"|DD| {abs_dd:.0%} >= 35%")
    if strategy_total_return < bench_total_return - 0.20 and strategy_sharpe < 1.0:
        reasons.append(f"return {strategy_total_return:+.0%} > 20pp below bench")
    if not reasons:
        reasons = ["combined Sharpe/DD/return below all upper-tier thresholds"]
    return TierVerdict("D", "; ".join(reasons))
