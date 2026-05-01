"""Shares-trading backtest engine.

Used for Phase 1 of the v2 validation plan: testing whether a signal has
edge on the underlying shares before any options-translation work. Much
simpler than the options engine — no BS pricing, no IV/spread modeling,
no per-trade-cap based on premium math, no DTE management.

Fills are at next-day open with a small bps slippage; exits at signal day's
close. Position sizing is a fraction of equity per trade (default 100%
since this is a single-strategy validation).

Strategies are reused: any Strategy that produces a Signal with a
direction (LONG/SHORT_FADE) can be run here. Option fields on the Signal
are ignored. Exit logic for IBS-on-shares is implemented locally in this
module rather than reusing src/positions/exits.py because the universal
options exits (premium stop, DTE) don't apply to shares.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Sequence
from zoneinfo import ZoneInfo

import pandas as pd

from src.indicators import atr
from src.indicators import ibs as ibs_ind
from src.strategies.base import Signal, SignalAction, Strategy

ET = ZoneInfo("America/New_York")


@dataclass
class SharesBacktestConfig:
    start: date
    end: date
    initial_capital: float = 8000.0
    allocation_pct: float = 1.0          # fraction of equity per entry
    max_concurrent: int = 1
    slippage_bps: float = 5.0            # 5 bps on share fills
    time_stop_days: int = 5              # 0 disables time stop
    enable_signal_only_mode: bool = False  # disables time stop too (raw signal edge)


@dataclass
class ShareTrade:
    trade_id: str
    underlying: str
    direction: str                       # "long" | "short_fade"
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    shares: int
    pnl: float
    reason: str
    days_held: int


@dataclass
class SharesBacktestResult:
    config: SharesBacktestConfig
    trades: list[ShareTrade]
    equity_curve: pd.Series
    skipped_signals: list[dict] = field(default_factory=list)


@dataclass
class _OpenSharePosition:
    trade_id: str
    underlying: str
    direction: SignalAction
    entry_date: date
    entry_price: float
    shares: int


class SharesBacktestEngine:
    """Daily-close-driven shares backtest.

    Per-day flow:
      1. Open phase  — fill any deferred entries at today's open
      2. Close phase — evaluate IBS exit conditions at today's close
      3. Strategy pass — run on_daily_close on each underlying, queue
         deferred entries for tomorrow's open
      4. Equity update at today's close (cash + open mark-to-market)
    """

    def __init__(
        self,
        config: SharesBacktestConfig,
        strategies: Sequence[Strategy],
        daily_bars: dict[str, pd.DataFrame],
    ):
        self.cfg = config
        self.strategies = list(strategies)
        self.daily_bars = daily_bars
        # Pre-build date -> row-index lookup tables per symbol so per-day
        # access is O(1) instead of O(n). Without this, an 8-year backtest
        # spends most of its time re-scanning DataFrames.
        self._date_idx: dict[str, dict[date, int]] = {}
        for sym, df in daily_bars.items():
            if df is None or df.empty:
                self._date_idx[sym] = {}
                continue
            self._date_idx[sym] = {
                (ts.date() if hasattr(ts, "date") else ts): i
                for i, ts in enumerate(df.index)
            }
        self.cash = config.initial_capital
        self.open_positions: list[_OpenSharePosition] = []
        self.deferred: list[tuple[Signal, date]] = []
        self.trades: list[ShareTrade] = []
        self.skipped: list[dict] = []
        self.equity_by_date: dict[date, float] = {}

    # --- Public ---------------------------------------------------------

    def run(self) -> SharesBacktestResult:
        all_dates = self._trading_dates()
        if not all_dates:
            raise ValueError(f"no daily bars in [{self.cfg.start}, {self.cfg.end}]")
        for d in all_dates:
            self._process_day(d)
        # Force-close anything still open at the end
        if all_dates:
            self._force_close_all(all_dates[-1])
        eq = pd.Series(self.equity_by_date).sort_index()
        return SharesBacktestResult(
            config=self.cfg, trades=self.trades, equity_curve=eq,
            skipped_signals=self.skipped,
        )

    # --- Daily driver ---------------------------------------------------

    def _process_day(self, today: date) -> None:
        # 1. Open phase
        ready = [(s, when) for (s, when) in self.deferred if when <= today]
        for sig, when in ready:
            self._execute_entry(sig, today)
            self.deferred.remove((sig, when))

        # 2. Close phase: evaluate exits
        self._evaluate_exits(today)

        # 3. Daily-close strategy pass
        next_open = self._next_session_date(today)
        for sym in ("SPY", "QQQ"):
            bars = self._bars_through(self.daily_bars.get(sym), today)
            if bars is None or bars.empty:
                continue
            for strat in self.strategies:
                sig = strat.on_daily_close(sym, bars)
                if sig is not None:
                    self.deferred.append((sig, next_open))

        # 4. Equity at close
        self.equity_by_date[today] = self._equity_at_close(today)

    def _execute_entry(self, sig: Signal, today: date) -> None:
        sym = sig.underlying
        df = self.daily_bars.get(sym)
        if df is None or df.empty:
            return
        i = self._date_idx[sym].get(today)
        if i is None:
            return
        open_price = float(df["open"].iloc[i])
        if open_price <= 0:
            return

        # Concurrent-position limit
        if len(self.open_positions) >= self.cfg.max_concurrent:
            self.skipped.append({
                "date": today.isoformat(), "underlying": sym,
                "reason": "max_concurrent",
            })
            return

        # Size: allocation_pct of current equity, divided by available slots
        equity = self._equity_at_open(today)
        budget = equity * self.cfg.allocation_pct / max(1, self.cfg.max_concurrent)
        slip = open_price * self.cfg.slippage_bps / 10_000
        fill_price = open_price + slip if sig.action == SignalAction.LONG else open_price - slip
        shares = int(budget // fill_price)
        if shares < 1:
            self.skipped.append({
                "date": today.isoformat(), "underlying": sym,
                "reason": "size_zero",
            })
            return

        cost = shares * fill_price
        if cost > self.cash:
            shares = int(self.cash // fill_price)
            if shares < 1:
                self.skipped.append({
                    "date": today.isoformat(), "underlying": sym,
                    "reason": "insufficient_cash",
                })
                return
            cost = shares * fill_price

        self.cash -= cost
        self.open_positions.append(_OpenSharePosition(
            trade_id=str(uuid.uuid4()),
            underlying=sym,
            direction=sig.action,
            entry_date=today,
            entry_price=fill_price,
            shares=shares,
        ))

    def _evaluate_exits(self, today: date) -> None:
        for pos in list(self.open_positions):
            df = self.daily_bars.get(pos.underlying)
            if df is None or df.empty:
                continue
            i = self._date_idx[pos.underlying].get(today)
            if i is None:
                continue
            today_close = float(df["close"].iloc[i])

            should_exit, reason = self._check_exit(pos, today, df)
            if not should_exit:
                continue
            slip = today_close * self.cfg.slippage_bps / 10_000
            exit_price = today_close - slip if pos.direction == SignalAction.LONG else today_close + slip
            self._close_position(pos, today, exit_price, reason)

    def _check_exit(
        self, pos: _OpenSharePosition, today: date, df: pd.DataFrame,
    ) -> tuple[bool, str]:
        # Time stop (skipped in signal-only mode)
        days_held = (today - pos.entry_date).days
        if not self.cfg.enable_signal_only_mode and self.cfg.time_stop_days > 0:
            if days_held >= self.cfg.time_stop_days:
                return True, "time_stop"

        i = self._date_idx.get(pos.underlying, {}).get(today)
        if i is None or i == 0:
            return False, ""

        today_high = float(df["high"].iloc[i])
        today_low = float(df["low"].iloc[i])
        today_close = float(df["close"].iloc[i])
        prior_high = float(df["high"].iloc[i - 1])
        prior_low = float(df["low"].iloc[i - 1])
        rng = today_high - today_low
        today_ibs = (today_close - today_low) / rng if rng > 0 else 0.5

        # IBS spec exit conditions
        if pos.direction == SignalAction.LONG:
            if today_close > prior_high:
                return True, "signal_close_above_prior_high"
            if today_ibs > 0.70:
                return True, "signal_ibs_above_70"
        else:  # SHORT_FADE on signal underlying (rare in this engine)
            if today_close < prior_low:
                return True, "signal_close_below_prior_low"
            if today_ibs < 0.30:
                return True, "signal_ibs_below_30"
        return False, ""

    def _close_position(
        self, pos: _OpenSharePosition, today: date, exit_price: float, reason: str,
    ) -> None:
        if pos.direction == SignalAction.LONG:
            pnl = (exit_price - pos.entry_price) * pos.shares
            self.cash += exit_price * pos.shares
        else:
            pnl = (pos.entry_price - exit_price) * pos.shares
            # Short share P&L is harder to model accurately; we keep it simple
            self.cash += (pos.entry_price + (pos.entry_price - exit_price)) * pos.shares

        self.open_positions.remove(pos)
        self.trades.append(ShareTrade(
            trade_id=pos.trade_id,
            underlying=pos.underlying,
            direction=pos.direction.value,
            entry_date=pos.entry_date,
            entry_price=pos.entry_price,
            exit_date=today,
            exit_price=exit_price,
            shares=pos.shares,
            pnl=pnl,
            reason=reason,
            days_held=(today - pos.entry_date).days,
        ))

    def _force_close_all(self, today: date) -> None:
        for pos in list(self.open_positions):
            df = self.daily_bars.get(pos.underlying)
            close = _row_value(df, today, "close") or pos.entry_price
            self._close_position(pos, today, close, "end_of_backtest")

    # --- Equity ---------------------------------------------------------

    def _equity_at_open(self, today: date) -> float:
        """Equity using yesterday's close as MTM (we're at today's open)."""
        prior = self._prev_trading_date(today)
        if prior is None:
            return self.cash + sum(p.shares * p.entry_price for p in self.open_positions)
        mtm = 0.0
        for p in self.open_positions:
            df = self.daily_bars.get(p.underlying)
            i = self._date_idx.get(p.underlying, {}).get(prior)
            close = float(df["close"].iloc[i]) if (i is not None and df is not None) else p.entry_price
            mtm += p.shares * close
        return self.cash + mtm

    def _equity_at_close(self, today: date) -> float:
        mtm = 0.0
        for p in self.open_positions:
            df = self.daily_bars.get(p.underlying)
            i = self._date_idx.get(p.underlying, {}).get(today)
            close = float(df["close"].iloc[i]) if (i is not None and df is not None) else p.entry_price
            mtm += p.shares * close
        return self.cash + mtm

    # --- Date helpers ---------------------------------------------------

    def _trading_dates(self) -> list[date]:
        spy = self.daily_bars.get("SPY")
        cal = (spy if spy is not None and not spy.empty else self.daily_bars.get("QQQ"))
        if cal is None or cal.empty:
            return []
        return [d.date() if hasattr(d, "date") else d
                for d in cal.index
                if self.cfg.start <= (d.date() if hasattr(d, "date") else d) <= self.cfg.end]

    def _bars_through(self, df: pd.DataFrame | None, today: date) -> pd.DataFrame | None:
        if df is None or df.empty:
            return None
        # Find symbol via identity match against cached frames
        sym = None
        for s, cached in self.daily_bars.items():
            if cached is df:
                sym = s
                break
        if sym is not None:
            i = self._date_idx[sym].get(today)
            if i is not None:
                return df.iloc[: i + 1]
        # Fallback (shouldn't happen normally)
        idx = df.index
        mask = pd.Series([(d.date() if hasattr(d, "date") else d) <= today for d in idx], index=idx)
        return df.loc[mask]

    def _prev_trading_date(self, today: date) -> date | None:
        spy = self.daily_bars.get("SPY")
        if spy is None or spy.empty:
            return None
        idx_map = self._date_idx.get("SPY", {})
        i = idx_map.get(today)
        if i is None or i == 0:
            return None
        ts = spy.index[i - 1]
        return ts.date() if hasattr(ts, "date") else ts

    @staticmethod
    def _next_session_date(today: date) -> date:
        d = today + timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d


def _row_value(df: pd.DataFrame | None, today: date, col: str) -> float | None:
    """Slow O(n) fallback for callers without an index map. The engine
    methods above use the cached date->index lookup directly."""
    if df is None or df.empty:
        return None
    # Fast path: try direct .loc[] on Timestamp
    try:
        ts = pd.Timestamp(today)
        if ts in df.index:
            v = df.at[ts, col]
            return None if pd.isna(v) else float(v)
    except Exception:
        pass
    # Slow path
    for ts, row in df.iterrows():
        d = ts.date() if hasattr(ts, "date") else ts
        if d == today:
            v = row.get(col)
            if v is None or pd.isna(v):
                return None
            return float(v)
    return None
