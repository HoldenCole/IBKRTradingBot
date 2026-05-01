"""Performance metrics over a closed-trade ledger + equity curve."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestResult, TradeRecord


@dataclass
class PerformanceMetrics:
    n_trades: int
    n_wins: int
    n_losses: int
    win_rate: float
    avg_win: float
    avg_loss: float
    expectancy: float
    profit_factor: float
    total_pnl: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe: float
    by_strategy: dict[str, dict] = field(default_factory=dict)
    by_reason: dict[str, int] = field(default_factory=dict)


def _strategy_breakdown(trades: list[TradeRecord]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for s in {t.strategy for t in trades}:
        sub = [t for t in trades if t.strategy == s]
        wins = [t for t in sub if t.pnl > 0]
        losses = [t for t in sub if t.pnl <= 0]
        out[s] = {
            "n_trades": len(sub),
            "win_rate": (len(wins) / len(sub)) if sub else 0.0,
            "total_pnl": sum(t.pnl for t in sub),
            "avg_win": (sum(t.pnl for t in wins) / len(wins)) if wins else 0.0,
            "avg_loss": (sum(t.pnl for t in losses) / len(losses)) if losses else 0.0,
        }
    return out


def _max_drawdown_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    return float(dd.min())


def _sharpe(equity: pd.Series, periods_per_year: int = 252) -> float:
    """Annualized Sharpe of daily returns. Risk-free assumed 0; close enough
    on a $8k account for a directional comparison.
    """
    if len(equity) < 2:
        return 0.0
    rets = equity.pct_change().dropna()
    if rets.empty or rets.std(ddof=0) == 0:
        return 0.0
    return float((rets.mean() / rets.std(ddof=0)) * math.sqrt(periods_per_year))


def compute_metrics(result: BacktestResult) -> PerformanceMetrics:
    trades = result.trades
    n = len(trades)
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    total_pnl = sum(t.pnl for t in trades)
    avg_win = (sum(t.pnl for t in wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(t.pnl for t in losses) / len(losses)) if losses else 0.0
    win_rate = (len(wins) / n) if n else 0.0

    gross_win = sum(t.pnl for t in wins)
    gross_loss = -sum(t.pnl for t in losses)  # positive number
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float("inf") if gross_win > 0 else 0.0
    expectancy = total_pnl / n if n else 0.0

    # Equity curve
    equity = result.equity_curve
    initial = result.config.initial_capital
    total_return_pct = float((equity.iloc[-1] - initial) / initial) if not equity.empty else 0.0

    by_reason: dict[str, int] = {}
    for t in trades:
        by_reason[t.reason] = by_reason.get(t.reason, 0) + 1

    return PerformanceMetrics(
        n_trades=n,
        n_wins=len(wins),
        n_losses=len(losses),
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        expectancy=expectancy,
        profit_factor=profit_factor,
        total_pnl=total_pnl,
        total_return_pct=total_return_pct,
        max_drawdown_pct=_max_drawdown_pct(equity),
        sharpe=_sharpe(equity),
        by_strategy=_strategy_breakdown(trades),
        by_reason=by_reason,
    )


def format_report(result: BacktestResult, m: PerformanceMetrics) -> str:
    lines: list[str] = []
    lines.append(f"=== Backtest Report ===")
    lines.append(f"Period: {result.config.start} → {result.config.end}")
    lines.append(f"Initial capital: ${result.config.initial_capital:,.0f}")
    lines.append("")
    lines.append(f"Trades:        {m.n_trades}  ({m.n_wins}W / {m.n_losses}L)")
    lines.append(f"Win rate:      {m.win_rate:.1%}")
    lines.append(f"Avg win:       ${m.avg_win:.2f}")
    lines.append(f"Avg loss:      ${m.avg_loss:.2f}")
    lines.append(f"Expectancy:    ${m.expectancy:.2f}/trade")
    lines.append(f"Profit factor: {m.profit_factor:.2f}")
    lines.append(f"Total PnL:     ${m.total_pnl:,.2f}")
    lines.append(f"Total return:  {m.total_return_pct:.1%}")
    lines.append(f"Max drawdown:  {m.max_drawdown_pct:.1%}")
    lines.append(f"Sharpe (ann.): {m.sharpe:.2f}")

    if m.by_strategy:
        lines.append("")
        lines.append("By strategy:")
        for s, d in m.by_strategy.items():
            lines.append(
                f"  {s:20s}  trades={d['n_trades']:3d}  "
                f"win%={d['win_rate']:.0%}  pnl=${d['total_pnl']:.0f}"
            )
    if m.by_reason:
        lines.append("")
        lines.append("Exit reasons:")
        for r, c in sorted(m.by_reason.items(), key=lambda x: -x[1]):
            lines.append(f"  {r:30s} {c}")
    if result.skipped_signals:
        lines.append("")
        lines.append(f"Suppressed signals: {len(result.skipped_signals)}")
        # Top reasons
        from collections import Counter
        c = Counter(s["reason"] for s in result.skipped_signals)
        for r, n in c.most_common(5):
            lines.append(f"  {r:30s} {n}")
    return "\n".join(lines)
