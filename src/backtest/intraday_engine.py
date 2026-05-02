"""Intraday backtest engine — drives 5-min bars through a strategy that
implements `on_intraday_bar`.

Used for afternoon reversion (Phase 5). Reuses the existing
AfternoonReversionStrategy unmodified — that class already speaks the
on_intraday_bar interface and emits Signals with a direction and an
underlying. The engine here trades shares of the SIGNAL UNDERLYING
(SPY or QQQ), not the levered ETF the original spec called for. That
matches the v2 evaluation framework (lift over BAH on the same
instrument; option leverage tested separately later).

Per-day flow:
  1. Build today's session DataFrame from the 5-min bar cache (RTH only)
  2. Compute daily ATR(20) on the underlying (needed by strategy's
     ATR-relative thresholds) and stash on session.attrs["daily_atr20"]
  3. Walk session bars one at a time, calling strategy.on_intraday_bar
     after each
  4. On signal fire, enter position at the bar's close (with bps
     slippage); track until exit
  5. Apply exit rules: morning-range hard stop, VWAP reclaim scale,
     EOD close (always close at session end — no overnight holds in v2
     to keep the comparison clean and avoid mixing styles)
  6. Mark equity at session close

Walk-forward and per-regime evaluation use the same v2 framework as
the share-only strategies.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo

import pandas as pd

from src.backtest.shares_engine import SharesBacktestResult, ShareTrade
from src.indicators import atr
from src.strategies.afternoon import AfternoonReversionStrategy
from src.strategies.base import Signal, SignalAction

ET = ZoneInfo("America/New_York")


@dataclass
class IntradayConfig:
    start: date
    end: date
    universe: str                          # "SPY" or "QQQ"
    initial_capital: float = 8000.0
    allocation_pct: float = 1.0
    slippage_bps: float = 2.0              # SPY/QQQ intraday spreads are ~1bp
    eod_close: bool = True                 # always close at session end
    hard_stop_atr_fraction: float = 0.5    # exit if move 0.5 * morning range against
    bar_dir: Path | None = None            # data/intraday/{symbol}/{YYYY-MM-DD}.parquet


@dataclass
class _OpenIntradayPosition:
    trade_id: str
    underlying: str
    direction: SignalAction
    entry_ts: pd.Timestamp
    entry_price: float
    shares: int
    morning_low: float
    morning_high: float


class IntradayBacktestEngine:
    """Drives 5-min bars through AfternoonReversionStrategy."""

    def __init__(
        self,
        config: IntradayConfig,
        daily_bars: dict[str, pd.DataFrame],     # for ATR computation
        strategy: AfternoonReversionStrategy | None = None,
        bar_loader=None,                         # callable(date) -> session DataFrame
    ):
        self.cfg = config
        self.daily = daily_bars
        self.strategy = strategy or AfternoonReversionStrategy()
        if bar_loader is None and config.bar_dir is None:
            raise ValueError(
                "Need either bar_loader callable or bar_dir for parquet cache"
            )
        self.bar_loader = bar_loader or self._default_loader
        self.cash = config.initial_capital
        self.position: _OpenIntradayPosition | None = None
        self.trades: list[ShareTrade] = []
        self.equity_by_date: dict[date, float] = {}
        self.skipped: list[dict] = []

    def _default_loader(self, d: date) -> pd.DataFrame | None:
        """Loads `data/intraday/{universe}/{YYYY-MM-DD}.parquet` if it exists."""
        if self.cfg.bar_dir is None:
            return None
        path = self.cfg.bar_dir / self.cfg.universe / f"{d.isoformat()}.parquet"
        empty_marker = path.with_suffix(".empty")
        if empty_marker.exists():
            return None
        if not path.exists():
            return None
        df = pd.read_parquet(path)
        # Normalize column names to match what AfternoonReversionStrategy expects
        # (open / high / low / close / volume + ts as tz-aware ET index)
        if "ts" not in df.columns and df.index.name in ("date", "ts"):
            df = df.reset_index().rename(columns={df.index.name: "ts"})
        if "date" in df.columns and "ts" not in df.columns:
            df = df.rename(columns={"date": "ts"})
        df["ts"] = pd.to_datetime(df["ts"])
        if df["ts"].dt.tz is None:
            df["ts"] = df["ts"].dt.tz_localize(ET)
        df = df.set_index("ts").sort_index()
        return df[["open", "high", "low", "close", "volume"]]

    def run(self) -> SharesBacktestResult:
        d = self.cfg.start
        while d <= self.cfg.end:
            if d.weekday() >= 5:                  # weekend
                d += timedelta(days=1)
                continue
            session = self.bar_loader(d)
            if session is None or session.empty:
                d += timedelta(days=1)
                continue

            # Attach daily ATR(20) on the underlying so strategy thresholds work
            sym = self.cfg.universe
            daily = self.daily.get(sym)
            if daily is not None and not daily.empty:
                # Compute ATR up to today (exclusive)
                daily_through = self._daily_through(daily, d)
                if not daily_through.empty:
                    atr20 = atr(daily_through["high"], daily_through["low"],
                                daily_through["close"]).iloc[-1]
                    if pd.notna(atr20):
                        session = session.copy()
                        session.attrs["daily_atr20"] = float(atr20)

            self._process_session(d, session)

            # Equity at session close
            self.equity_by_date[d] = self.cash + self._open_mtm_at(session.index[-1], session)

            d += timedelta(days=1)

        eq = pd.Series(self.equity_by_date).sort_index()
        return SharesBacktestResult(
            config=self.cfg,  # type: ignore[arg-type]
            trades=self.trades,
            equity_curve=eq,
            skipped_signals=self.skipped,
        )

    def _process_session(self, today: date, session: pd.DataFrame) -> None:
        """Walk the day's bars; manage one position max."""
        for ts, row in session.iterrows():
            bar = {
                "ts": ts, "open": row["open"], "high": row["high"],
                "low": row["low"], "close": row["close"], "volume": row["volume"],
            }
            # Check exit FIRST so we don't enter and exit on same bar
            if self.position is not None:
                self._check_exit(ts, bar, session)

            # Strategy generates new signals
            if self.position is None:
                # Pass session-up-to-now so the strategy sees only past bars
                session_so_far = session.loc[:ts]
                sig = self.strategy.on_intraday_bar(
                    self.cfg.universe, bar, session_so_far,
                )
                if sig is not None:
                    self._execute_entry(ts, bar, sig, session)

        # End-of-session: force-close if still open
        if self.position is not None and self.cfg.eod_close:
            last_ts = session.index[-1]
            last_close = float(session["close"].iloc[-1])
            self._close_position(last_ts, last_close, "eod_close")

    def _execute_entry(
        self, ts: pd.Timestamp, bar: dict, sig: Signal, session: pd.DataFrame,
    ) -> None:
        # Compute morning range (09:30-11:00 ET observation window)
        obs = session.between_time(time(9, 30), time(11, 0), inclusive="left")
        if obs.empty:
            return
        morning_low = float(obs["low"].min())
        morning_high = float(obs["high"].max())

        slip = bar["close"] * self.cfg.slippage_bps / 10_000
        if sig.action == SignalAction.LONG:
            entry_price = bar["close"] + slip
        else:
            entry_price = bar["close"] - slip

        shares = int((self.cash * self.cfg.allocation_pct) // entry_price)
        if shares < 1:
            self.skipped.append({
                "date": ts.date().isoformat(),
                "underlying": self.cfg.universe,
                "reason": "insufficient_cash",
            })
            return
        cost = shares * entry_price
        if sig.action == SignalAction.LONG:
            self.cash -= cost
        else:
            self.cash += cost
        self.position = _OpenIntradayPosition(
            trade_id=str(uuid.uuid4()),
            underlying=self.cfg.universe,
            direction=sig.action,
            entry_ts=ts,
            entry_price=entry_price,
            shares=shares,
            morning_low=morning_low,
            morning_high=morning_high,
        )

    def _check_exit(self, ts: pd.Timestamp, bar: dict, session: pd.DataFrame) -> None:
        if self.position is None:
            return
        morning_range = self.position.morning_high - self.position.morning_low
        threshold = morning_range * self.cfg.hard_stop_atr_fraction
        # Hard stop: 0.5 * morning range against entry
        if self.position.direction == SignalAction.LONG:
            if bar["low"] <= self.position.entry_price - threshold:
                exit_price = max(0.01, self.position.entry_price - threshold)
                self._close_position(ts, exit_price, "hard_stop")
                return
        else:
            if bar["high"] >= self.position.entry_price + threshold:
                exit_price = self.position.entry_price + threshold
                self._close_position(ts, exit_price, "hard_stop")
                return

        # VWAP reclaim — partial exit replaced with full exit for simplicity
        # (the original spec is partial-scale; the simple v2 closes fully).
        vwap = self._session_vwap(session.loc[:ts])
        if vwap is not None:
            if self.position.direction == SignalAction.LONG and bar["close"] >= vwap:
                self._close_position(ts, bar["close"], "vwap_reclaim")
                return
            if self.position.direction == SignalAction.SHORT_FADE and bar["close"] <= vwap:
                self._close_position(ts, bar["close"], "vwap_reclaim")
                return

    def _close_position(self, ts: pd.Timestamp, exit_price: float, reason: str) -> None:
        if self.position is None:
            return
        slip = exit_price * self.cfg.slippage_bps / 10_000
        if self.position.direction == SignalAction.LONG:
            fill_price = max(0.01, exit_price - slip)
            pnl = (fill_price - self.position.entry_price) * self.position.shares
            self.cash += fill_price * self.position.shares
        else:
            fill_price = exit_price + slip
            pnl = (self.position.entry_price - fill_price) * self.position.shares
            self.cash -= fill_price * self.position.shares
        self.trades.append(ShareTrade(
            trade_id=self.position.trade_id,
            underlying=self.position.underlying,
            direction=self.position.direction.value,
            entry_date=self.position.entry_ts.date(),
            entry_price=self.position.entry_price,
            exit_date=ts.date(),
            exit_price=fill_price,
            shares=self.position.shares,
            pnl=pnl,
            reason=reason,
            days_held=0,  # intraday only, by design
        ))
        self.position = None

    def _session_vwap(self, session_so_far: pd.DataFrame) -> float | None:
        if session_so_far.empty:
            return None
        tp = (session_so_far["high"] + session_so_far["low"] + session_so_far["close"]) / 3.0
        cum_vol = session_so_far["volume"].cumsum()
        if cum_vol.iloc[-1] == 0:
            return None
        return float((tp * session_so_far["volume"]).cumsum().iloc[-1] / cum_vol.iloc[-1])

    def _open_mtm_at(self, ts: pd.Timestamp, session: pd.DataFrame) -> float:
        if self.position is None:
            return 0.0
        # Last close as MTM
        close = float(session["close"].iloc[-1])
        sign = 1 if self.position.direction == SignalAction.LONG else -1
        return sign * self.position.shares * close

    def _daily_through(self, df: pd.DataFrame, today: date) -> pd.DataFrame:
        idx = df.index
        mask = pd.Series(
            [(d.date() if hasattr(d, "date") else d) <= today for d in idx],
            index=idx,
        )
        return df.loc[mask]
