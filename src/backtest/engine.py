"""Bar-level backtest for the CL1/USO spread strategy.

Inputs are two 1-min OHLC frames (CL and USO). Bars are inner-joined on
timestamp so the strategy only ever sees minutes where both instruments
printed — the same synchronization rule used live.

Fills: signals generated on bar t execute at bar t+1's USO open (falling
back to close when no open column), with slippage and per-share commission
applied. Signals on the final bar are executed at that bar's close so no
position survives the backtest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.strategies.base import Action
from src.strategies.cl1_uso_spread import Cl1UsoSpreadStrategy, PairBar, SpreadParams


@dataclass
class BacktestConfig:
    position_usd: float = 500.0
    slippage_bps: float = 2.0
    commission_per_share: float = 0.005
    min_commission: float = 1.0
    params: SpreadParams = field(default_factory=SpreadParams)


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    equity: pd.Series
    metrics: dict

    def summary(self) -> str:
        lines = ["=== CL1/USO Spread Backtest ==="]
        for key, value in self.metrics.items():
            lines.append(f"{key:>22}: {value}")
        return "\n".join(lines)


def align_pair(cl: pd.DataFrame, uso: pd.DataFrame) -> pd.DataFrame:
    """Inner-join the two bar frames on timestamp."""
    df = pd.DataFrame(
        {
            "cl_close": cl["close"],
            "uso_close": uso["close"],
            "uso_open": uso["open"] if "open" in uso.columns else uso["close"],
        }
    ).dropna()
    if df.empty:
        raise ValueError("No overlapping timestamps between CL and USO data")
    return df


def _fill_price(raw: float, side: int, slippage_bps: float) -> float:
    # side +1 = we buy (pay up), -1 = we sell (give up)
    return raw * (1 + side * slippage_bps / 10_000)


def run_backtest(
    cl: pd.DataFrame, uso: pd.DataFrame, config: BacktestConfig | None = None
) -> BacktestResult:
    config = config or BacktestConfig()
    df = align_pair(cl, uso)
    strategy = Cl1UsoSpreadStrategy(params=config.params)

    timestamps = df.index.to_pydatetime()
    n = len(df)

    trades: list[dict] = []
    open_trade: dict | None = None
    realized = 0.0
    equity_points: list[tuple[pd.Timestamp, float]] = []

    def commission(shares: int) -> float:
        return max(config.min_commission, shares * config.commission_per_share)

    def execute(signal, i: int) -> None:
        nonlocal open_trade, realized
        # Fill on the next bar's open; last-bar signals fill at that close.
        if i + 1 < n:
            fill_idx, raw = i + 1, float(df["uso_open"].iloc[i + 1])
        else:
            fill_idx, raw = i, float(df["uso_close"].iloc[i])
        ts = df.index[fill_idx]

        if signal.action is Action.CLOSE:
            if open_trade is None:
                return
            side = open_trade["side"]  # +1 long, -1 short
            price = _fill_price(raw, -side, config.slippage_bps)
            shares = open_trade["shares"]
            pnl = side * (price - open_trade["entry_price"]) * shares - commission(shares)
            realized += pnl
            trades.append(
                {
                    **open_trade,
                    "exit_ts": ts,
                    "exit_price": price,
                    "exit_reason": signal.reason,
                    "pnl": pnl,
                }
            )
            open_trade = None
        else:
            side = 1 if signal.action is Action.BUY else -1
            price = _fill_price(raw, side, config.slippage_bps)
            shares = int(config.position_usd // price)
            if shares < 1:
                strategy.position = None  # entry unfillable at this size
                return
            realized -= commission(shares)
            open_trade = {
                "side": side,
                "entry_ts": ts,
                "entry_price": price,
                "shares": shares,
                "entry_reason": signal.reason,
            }

    for i in range(n):
        bar = PairBar(
            ts=timestamps[i],
            cl_close=float(df["cl_close"].iloc[i]),
            uso_close=float(df["uso_close"].iloc[i]),
        )
        signal = strategy.on_bar(bar)
        if signal is not None:
            execute(signal, i)

        mark = 0.0
        if open_trade is not None:
            mark = open_trade["side"] * (bar.uso_close - open_trade["entry_price"]) * open_trade["shares"]
        equity_points.append((df.index[i], realized + mark))

    # Safety: force-close anything still open (shouldn't happen with EOD flatten).
    if open_trade is not None:
        from src.strategies.base import Signal

        execute(Signal(action=Action.CLOSE, reason="backtest_end"), n - 1)
        equity_points[-1] = (df.index[-1], realized)

    trades_df = pd.DataFrame(trades)
    equity = pd.Series(dict(equity_points), name="equity")
    metrics = _metrics(trades_df, equity, config)
    return BacktestResult(trades=trades_df, equity=equity, metrics=metrics)


def _metrics(trades: pd.DataFrame, equity: pd.Series, config: BacktestConfig) -> dict:
    if trades.empty:
        return {"n_trades": 0, "note": "no trades generated"}
    pnl = trades["pnl"]
    daily = equity.groupby(equity.index.date).last().diff().dropna()
    sharpe = float("nan")
    if len(daily) > 1 and daily.std() > 0:
        sharpe = float(daily.mean() / daily.std() * np.sqrt(252))
    drawdown = equity - equity.cummax()
    hold = (trades["exit_ts"] - trades["entry_ts"]).dt.total_seconds() / 60
    return {
        "n_trades": len(trades),
        "total_pnl": f"${pnl.sum():.2f}",
        "win_rate": f"{(pnl > 0).mean():.1%}",
        "avg_pnl_per_trade": f"${pnl.mean():.2f}",
        "median_hold_minutes": f"{hold.median():.0f}",
        "max_drawdown": f"${drawdown.min():.2f}",
        "daily_sharpe": f"{sharpe:.2f}",
        "long_trades": int((trades["side"] == 1).sum()),
        "short_trades": int((trades["side"] == -1).sum()),
        "position_usd": f"${config.position_usd:.0f}",
    }
