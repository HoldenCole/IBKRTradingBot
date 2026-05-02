"""VIX spike fade engine — long volatility on regime-shift signals.

The signal: when VIX rises sharply (or above an absolute threshold), enter
a long-volatility position via VXX. Exit when VIX normalizes or after
a short time stop (vol ETPs bleed structurally; never carry long).

Three signal variants per `reports/diversifier_candidates/VIX_SPIKE_FADE_SCOPE.md`:

  v0 — Threshold trigger:
    Entry: VIX_today > 25 AND VIX_today > 1.2 * VIX_5d_ago
    Exit: VIX_today < 20 OR 5-day time stop

  v1 — Spike-rate trigger:
    Entry: VIX_today / VIX_yesterday > 1.20  (one-day jump > 20%)
    Exit: 3-day time stop OR VIX returns within 10% of pre-spike level

  v2 — SPX-down + VIX-up combined:
    Entry: SPY one-day return < -2% AND VIX > 22
    Exit: 5-day time stop

The strategy trades VXX shares, not options. VXX has structural
negative carry (~30-50%/year) so the strategy must be quick. Exits
should fire fast.

Engine is focused (single instrument: VXX) rather than reused from
SharesBacktestEngine which iterates over SPY/QQQ universe.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

import pandas as pd

from src.backtest.shares_engine import SharesBacktestResult, ShareTrade


class SignalVariant(str, Enum):
    V0_THRESHOLD = "v0_threshold"
    V1_SPIKE_RATE = "v1_spike_rate"
    V2_SPX_DOWN = "v2_spx_down"


@dataclass
class VixSpikeConfig:
    start: date
    end: date
    initial_capital: float = 8000.0
    allocation_pct: float = 1.0
    slippage_bps: float = 10.0          # VXX is more volatile/wider spread than SPY/QQQ
    variant: SignalVariant = SignalVariant.V0_THRESHOLD

    # v0 thresholds
    v0_vix_threshold: float = 25.0
    v0_vix_5d_multiplier: float = 1.2
    v0_exit_vix: float = 20.0
    v0_time_stop_days: int = 5

    # v1 thresholds
    v1_one_day_multiplier: float = 1.20
    v1_time_stop_days: int = 3
    v1_exit_recovery_pct: float = 0.10

    # v2 thresholds
    v2_spx_down_pct: float = -0.02
    v2_vix_threshold: float = 22.0
    v2_time_stop_days: int = 5


@dataclass
class _OpenVixPosition:
    trade_id: str
    entry_date: date
    entry_price: float        # VXX entry price
    shares: int
    entry_vix: float          # VIX at signal day
    pre_spike_vix: float      # for v1 recovery exit


class VixSpikeFadeEngine:
    """Long VXX on VIX spike triggers, exits on VIX normalization."""

    def __init__(
        self,
        config: VixSpikeConfig,
        vix: pd.DataFrame,         # FRED 'close' column, date index
        vxx: pd.DataFrame,         # FMP daily OHLCV, date index
        spy: pd.DataFrame | None = None,  # required for v2
    ):
        self.cfg = config
        self.vix = self._slice(vix)
        self.vxx = self._slice(vxx)
        self.spy = self._slice(spy) if spy is not None else None
        if config.variant == SignalVariant.V2_SPX_DOWN and self.spy is None:
            raise ValueError("v2 variant requires SPY bars")
        self.cash = config.initial_capital
        self.position: _OpenVixPosition | None = None
        self.trades: list[ShareTrade] = []
        self.equity_by_date: dict[date, float] = {}

        # Pre-build date->index maps for O(1) lookup
        self._vix_idx = {self._d(ts): i for i, ts in enumerate(self.vix.index)}
        self._vxx_idx = {self._d(ts): i for i, ts in enumerate(self.vxx.index)}
        self._spy_idx = ({self._d(ts): i for i, ts in enumerate(self.spy.index)}
                         if self.spy is not None else {})

    @staticmethod
    def _d(ts) -> date:
        return ts.date() if hasattr(ts, "date") else ts

    def _slice(self, df: pd.DataFrame | None) -> pd.DataFrame | None:
        if df is None or df.empty:
            return df
        idx = [self._d(ts) for ts in df.index]
        mask = pd.Series(
            [self.cfg.start <= d <= self.cfg.end for d in idx],
            index=df.index,
        )
        return df.loc[mask].copy()

    def run(self) -> SharesBacktestResult:
        """Walk trading days; check entry on each, check exit if open."""
        # Use VXX's calendar as the trading-day index (we trade VXX)
        trading_dates = sorted(self._d(ts) for ts in self.vxx.index)
        if not trading_dates:
            return SharesBacktestResult(
                config=self.cfg,  # type: ignore[arg-type]
                trades=[], equity_curve=pd.Series(dtype=float), skipped_signals=[],
            )

        for d in trading_dates:
            # 1. Check exit if a position is open
            if self.position is not None:
                self._check_exit(d)

            # 2. Check entry if no position
            if self.position is None:
                self._check_entry(d)

            # 3. Mark equity at close
            self.equity_by_date[d] = self._equity_at_close(d)

        # Force-close anything still open at end of backtest
        if self.position is not None:
            last = trading_dates[-1]
            self._close_at_close(last, reason="end_of_backtest")

        eq = pd.Series(self.equity_by_date).sort_index()
        return SharesBacktestResult(
            config=self.cfg,  # type: ignore[arg-type]
            trades=self.trades,
            equity_curve=eq,
            skipped_signals=[],
        )

    # --- Entry logic ---

    def _check_entry(self, today: date) -> None:
        v_idx = self._vix_idx.get(today)
        if v_idx is None or v_idx < 5:
            return
        vix_today = float(self.vix["close"].iloc[v_idx])

        triggered, pre_spike_vix = self._signal_triggered(today, v_idx, vix_today)
        if not triggered:
            return

        x_idx = self._vxx_idx.get(today)
        if x_idx is None:
            return
        vxx_close = float(self.vxx["close"].iloc[x_idx])
        if vxx_close <= 0:
            return

        slip = vxx_close * self.cfg.slippage_bps / 10_000.0
        entry_price = vxx_close + slip
        budget = self.cash * self.cfg.allocation_pct
        shares = int(budget // entry_price)
        if shares < 1:
            return

        cost = shares * entry_price
        self.cash -= cost
        self.position = _OpenVixPosition(
            trade_id=str(uuid.uuid4()),
            entry_date=today,
            entry_price=entry_price,
            shares=shares,
            entry_vix=vix_today,
            pre_spike_vix=pre_spike_vix,
        )

    def _signal_triggered(self, today: date, v_idx: int, vix_today: float) -> tuple[bool, float]:
        cfg = self.cfg
        if cfg.variant == SignalVariant.V0_THRESHOLD:
            vix_5d_ago = float(self.vix["close"].iloc[v_idx - 5])
            triggered = (vix_today > cfg.v0_vix_threshold
                         and vix_today > cfg.v0_vix_5d_multiplier * vix_5d_ago)
            return triggered, vix_5d_ago

        if cfg.variant == SignalVariant.V1_SPIKE_RATE:
            vix_yesterday = float(self.vix["close"].iloc[v_idx - 1])
            triggered = vix_today / vix_yesterday > cfg.v1_one_day_multiplier
            return triggered, vix_yesterday

        if cfg.variant == SignalVariant.V2_SPX_DOWN:
            if self.spy is None:
                return False, 0.0
            s_idx = self._spy_idx.get(today)
            if s_idx is None or s_idx < 1:
                return False, 0.0
            spy_today = float(self.spy["close"].iloc[s_idx])
            spy_yesterday = float(self.spy["close"].iloc[s_idx - 1])
            spy_ret = (spy_today - spy_yesterday) / spy_yesterday
            triggered = (spy_ret < cfg.v2_spx_down_pct
                         and vix_today > cfg.v2_vix_threshold)
            return triggered, vix_today

        return False, 0.0

    # --- Exit logic ---

    def _check_exit(self, today: date) -> None:
        if self.position is None:
            return
        cfg = self.cfg
        days_held = (today - self.position.entry_date).days
        v_idx = self._vix_idx.get(today)
        vix_today = float(self.vix["close"].iloc[v_idx]) if v_idx is not None else 0.0

        should_exit = False
        reason = ""
        if cfg.variant == SignalVariant.V0_THRESHOLD:
            if vix_today < cfg.v0_exit_vix:
                should_exit, reason = True, "vix_normalized"
            elif days_held >= cfg.v0_time_stop_days:
                should_exit, reason = True, "time_stop"

        elif cfg.variant == SignalVariant.V1_SPIKE_RATE:
            recovery_target = self.position.pre_spike_vix * (1 + cfg.v1_exit_recovery_pct)
            if vix_today <= recovery_target:
                should_exit, reason = True, "vix_recovered"
            elif days_held >= cfg.v1_time_stop_days:
                should_exit, reason = True, "time_stop"

        elif cfg.variant == SignalVariant.V2_SPX_DOWN:
            if days_held >= cfg.v2_time_stop_days:
                should_exit, reason = True, "time_stop"
            elif vix_today < 18.0:
                should_exit, reason = True, "vix_normalized"

        if should_exit:
            self._close_at_close(today, reason)

    def _close_at_close(self, today: date, reason: str) -> None:
        if self.position is None:
            return
        x_idx = self._vxx_idx.get(today)
        if x_idx is None:
            # No VXX bar for today; defer until next valid bar
            return
        vxx_close = float(self.vxx["close"].iloc[x_idx])
        slip = vxx_close * self.cfg.slippage_bps / 10_000.0
        exit_price = max(0.01, vxx_close - slip)
        pnl = (exit_price - self.position.entry_price) * self.position.shares
        self.cash += exit_price * self.position.shares
        self.trades.append(ShareTrade(
            trade_id=self.position.trade_id,
            underlying="VXX",
            direction="long",
            entry_date=self.position.entry_date,
            entry_price=self.position.entry_price,
            exit_date=today,
            exit_price=exit_price,
            shares=self.position.shares,
            pnl=pnl,
            reason=reason,
            days_held=(today - self.position.entry_date).days,
        ))
        self.position = None

    def _equity_at_close(self, today: date) -> float:
        if self.position is None:
            return self.cash
        x_idx = self._vxx_idx.get(today)
        if x_idx is None:
            return self.cash + self.position.shares * self.position.entry_price
        close = float(self.vxx["close"].iloc[x_idx])
        return self.cash + self.position.shares * close
