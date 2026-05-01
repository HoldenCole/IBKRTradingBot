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
    # Step 1 additions: holding-period buckets for signal exits, and the
    # distribution of where premium-stops actually filled.
    signal_exit_by_hold: dict[str, dict] = field(default_factory=dict)
    stop_fill_distribution: dict[str, int] = field(default_factory=dict)


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


def _signal_exit_by_hold(trades: list[TradeRecord]) -> dict[str, dict]:
    sig = [t for t in trades if t.reason == "signal_exit"]
    buckets: dict[str, list[float]] = {"0d": [], "1d": [], "2d": [], "3d": [], "4+d": []}
    for t in sig:
        h = (t.exit_time - t.entry_time).days
        key = "4+d" if h >= 4 else f"{h}d"
        buckets[key].append(t.pnl)
    out: dict[str, dict] = {}
    for k, pnls in buckets.items():
        if not pnls:
            continue
        wins = sum(1 for x in pnls if x > 0)
        out[k] = {
            "n_trades": len(pnls),
            "win_rate": wins / len(pnls),
            "total_pnl": sum(pnls),
            "avg_pnl": sum(pnls) / len(pnls),
        }
    return out


def _stop_fill_distribution(trades: list[TradeRecord]) -> dict[str, int]:
    """Bucket premium_stop fills by % loss vs entry premium.
    Label is the loss range (e.g. -50% to -55% means we kept 45-50% of premium).
    """
    stops = [t for t in trades if t.reason == "premium_stop" and t.entry_premium > 0]
    # Each row: (lower-ratio, upper-ratio, label-as-loss-range)
    # Ratio = exit_premium / entry_premium, so ratio 0.45-0.50 -> loss 50-55%.
    edges = [(0.50, 0.55, "-45% to -50%"),
             (0.45, 0.50, "-50% to -55%"),
             (0.40, 0.45, "-55% to -60%"),
             (0.35, 0.40, "-60% to -65%"),
             (0.25, 0.35, "-65% to -75%"),
             (0.0,  0.25, "worse than -75%")]
    out: dict[str, int] = {label: 0 for _, _, label in edges}
    for t in stops:
        ratio = t.exit_premium / t.entry_premium
        for lo, hi, label in edges:
            if lo <= ratio < hi or (lo == 0.0 and ratio < 0.25):
                out[label] += 1
                break
    return out


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
        signal_exit_by_hold=_signal_exit_by_hold(trades),
        stop_fill_distribution=_stop_fill_distribution(trades),
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

    if m.signal_exit_by_hold:
        lines.append("")
        lines.append("Signal-exit P&L by holding period:")
        for k in ("0d", "1d", "2d", "3d", "4+d"):
            d = m.signal_exit_by_hold.get(k)
            if not d:
                continue
            lines.append(
                f"  {k:4s}  n={d['n_trades']:3d}  win%={d['win_rate']:.0%}  "
                f"total=${d['total_pnl']:>+7.0f}  avg=${d['avg_pnl']:>+6.0f}"
            )

    if m.stop_fill_distribution and any(m.stop_fill_distribution.values()):
        lines.append("")
        lines.append("Premium-stop fill distribution:")
        for label, count in m.stop_fill_distribution.items():
            if count:
                lines.append(f"  {label:20s} {count}")
    if result.skipped_signals:
        lines.append("")
        lines.append(f"Suppressed signals: {len(result.skipped_signals)}")
        # Top reasons
        from collections import Counter
        c = Counter(s["reason"] for s in result.skipped_signals)
        for r, n in c.most_common(5):
            lines.append(f"  {r:30s} {n}")
    return "\n".join(lines)
