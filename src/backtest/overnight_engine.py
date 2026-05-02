"""Overnight drift engine — buy at close T, sell at next-day open.

Minimal, focused engine for the well-documented overnight-drift edge:
SPY/QQQ overnight returns have been historically positive about
57-60% of the time, while the day-session contributes ~0% on
average. This engine tests whether that edge survives 2018-2026
out-of-sample (published evidence suggests it may have weakened
in recent years).

Mechanics:
  - One position at a time on a single underlying (SPY OR QQQ).
  - Every trading day enter at today's close, exit at tomorrow's open.
  - Slippage applied to both legs (default 5 bps each side).
  - Position sizing: floor(equity / close_price) shares per night.
  - Equity curve marked at next-day open after exit.

Reuses ShareTrade and SharesBacktestResult so the existing
format_v2_report works on the output. Reuses Sortino-aware tier
classifier.

This is NOT a Strategy in the framework sense — every day is a buy.
There is no signal logic to test.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.backtest.shares_engine import (
    SharesBacktestResult,
    ShareTrade,
)


@dataclass
class OvernightConfig:
    start: date
    end: date
    universe: str                        # "SPY" or "QQQ"
    initial_capital: float = 8000.0
    allocation_pct: float = 1.0          # fraction of equity per overnight position
    slippage_bps: float = 5.0            # 5 bps each leg
    enabled: bool = True                 # if False, returns empty result


class OvernightDriftEngine:
    """Always-long overnight on a single underlying."""

    def __init__(self, config: OvernightConfig, daily_bars: dict[str, pd.DataFrame]):
        self.cfg = config
        df = daily_bars.get(config.universe)
        if df is None or df.empty:
            raise ValueError(f"no daily bars for {config.universe!r}")
        # Filter to date range
        idx = [d.date() if hasattr(d, "date") else d for d in df.index]
        mask = pd.Series(
            [config.start <= d <= config.end for d in idx],
            index=df.index,
        )
        self.bars = df.loc[mask].copy()
        self.cash = config.initial_capital
        self.trades: list[ShareTrade] = []
        self.equity_by_date: dict[date, float] = {}

    def run(self) -> SharesBacktestResult:
        if self.bars.empty:
            return SharesBacktestResult(
                config=self.cfg,  # type: ignore[arg-type]
                trades=[], equity_curve=pd.Series(dtype=float),
                skipped_signals=[],
            )

        sym = self.cfg.universe
        slip = self.cfg.slippage_bps / 10_000.0

        for i in range(len(self.bars) - 1):
            today_ts = self.bars.index[i]
            tomorrow_ts = self.bars.index[i + 1]
            today_d = today_ts.date() if hasattr(today_ts, "date") else today_ts
            tomorrow_d = tomorrow_ts.date() if hasattr(tomorrow_ts, "date") else tomorrow_ts

            close_today = float(self.bars["close"].iloc[i])
            open_tomorrow = float(self.bars["open"].iloc[i + 1])

            # Entry at today's close (we pay slip going long)
            entry_price = close_today * (1 + slip)
            if entry_price <= 0:
                self.equity_by_date[today_d] = self.cash
                continue
            budget = self.cash * self.cfg.allocation_pct
            shares = int(budget // entry_price)
            if shares < 1:
                self.equity_by_date[today_d] = self.cash
                continue

            cost = shares * entry_price
            self.cash -= cost
            # Mark equity at today's close (after entry but no MTM gain yet)
            self.equity_by_date[today_d] = self.cash + shares * close_today

            # Exit at tomorrow's open (we receive slip going short out of position)
            exit_price = open_tomorrow * (1 - slip)
            self.cash += exit_price * shares

            pnl = (exit_price - entry_price) * shares
            self.trades.append(ShareTrade(
                trade_id=str(uuid.uuid4()),
                underlying=sym,
                direction="long",
                entry_date=today_d,
                entry_price=entry_price,
                exit_date=tomorrow_d,
                exit_price=exit_price,
                shares=shares,
                pnl=pnl,
                reason="overnight_exit",
                days_held=(tomorrow_d - today_d).days,
            ))

            # Equity at tomorrow's open (which is when we close)
            # We mark at tomorrow's CLOSE for the equity curve so it's
            # comparable to other strategies (close-to-close daily returns).
            close_tomorrow = float(self.bars["close"].iloc[i + 1])
            # Position is flat at this point; equity = cash
            self.equity_by_date[tomorrow_d] = self.cash

        eq = pd.Series(self.equity_by_date).sort_index()
        return SharesBacktestResult(
            config=self.cfg,  # type: ignore[arg-type]
            trades=self.trades,
            equity_curve=eq,
            skipped_signals=[],
        )
