"""LEAPS engine for the BAH-on-trend rule.

Trades long-dated SPY calls based on the SMA(50)/(200) bull-trend filter.
Per-day flow:

  1. Signal check: filter ON/OFF on signal underlying (SPY close)
  2. If ON and no position: buy LEAPS at target delta + tenor + sizing pct
  3. If ON and position exists: check if needs roll (remaining DTE < threshold)
  4. If OFF and position exists: sell at bid
  5. Daily MTM: re-price option at current spot, IV (proxied from VIX),
     remaining DTE; equity = cash + n_contracts * option_value * 100

Position state per LEAPS contract:
  - entry_date, exit_date, strike, expiry, n_contracts (fractional allowed)
  - entry_premium, exit_premium
  - hold_days (used for LTCG/STCG tax classification)

Tax classification (per IRS rules for LEAPS held to sale or expiration):
  - Hold > 365 calendar days: LTCG (15-20% federal)
  - Hold ≤ 365 days: STCG (24-37% federal)
  - LEAPS roll = sale of old + purchase of new. Each leg has its own
    holding period.

Spread modeling: 2% of mid bid-ask spread on SPY LEAPS ATM/near-ITM
(consistent with retail experience). Half-spread on each side of fill.

IV proxy: VIX × 1.05 (12mo tenor) or VIX × 1.08 (18mo tenor) — slightly
above-VIX to reflect SPX term structure averaging slightly upward-sloping.
Documented assumption; alternatives (VXMT, VIX1Y) require additional data.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from src.backtest.options import (
    OptionParams,
    black_scholes_call,
    black_scholes_call_delta,
    find_strike_for_delta,
)


@dataclass
class LeapsConfig:
    start: date
    end: date
    initial_capital: float = 8000.0
    target_delta: float = 0.80
    tenor_months: int = 18
    sizing_pct: float = 0.60          # fraction of equity in LEAPS premium
    roll_when_dte_le: int = 180       # roll when ≤ N days remaining
    spread_pct_of_mid: float = 0.02   # 2% bid-ask
    risk_free: float = 0.04           # constant 4% (modern average)
    div_yield: float = 0.015          # SPY ~1.5%
    vix_tenor_multiplier: float = 1.05  # VIX × this for IV at given tenor
    sma_fast: int = 50
    sma_slow: int = 200


@dataclass
class LeapsTrade:
    """Realized LEAPS trade — opened and closed."""
    trade_id: str
    open_date: date
    close_date: date
    strike: float
    expiry: date
    n_contracts: float          # fractional allowed
    entry_premium: float        # per-share, mid-price
    entry_fill: float           # per-share, including half-spread paid
    exit_premium: float         # per-share, mid at close
    exit_fill: float            # per-share, less half-spread
    pnl: float                  # dollars (per-share P&L × shares × 100)
    hold_days: int
    reason: str                 # "filter_off", "roll", "end_of_backtest"
    iv_at_entry: float
    iv_at_exit: float


@dataclass
class LeapsResult:
    config: LeapsConfig
    trades: list[LeapsTrade]
    equity_curve: pd.Series          # daily, dated
    realized_pnl: float
    final_cash: float
    final_position_value: float


@dataclass
class _OpenLeapsPosition:
    open_date: date
    strike: float
    expiry: date
    n_contracts: float
    entry_premium: float
    entry_fill: float
    iv_at_entry: float


class LeapsEngine:
    def __init__(
        self, config: LeapsConfig,
        spy_bars: pd.DataFrame,                 # signal + spot
        vix_series: pd.Series,                  # VIX index daily
    ):
        self.cfg = config
        self.spy = self._slice(spy_bars)
        self.vix = self._slice_series(vix_series)
        self.cash = config.initial_capital
        self.position: _OpenLeapsPosition | None = None
        self.trades: list[LeapsTrade] = []
        self.equity_by_date: dict[date, float] = {}

        # Pre-build date->index map
        self._spy_idx = {self._d(ts): i for i, ts in enumerate(self.spy.index)}

    @staticmethod
    def _d(ts) -> date:
        return ts.date() if hasattr(ts, "date") else ts

    def _slice(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        idx = [self._d(ts) for ts in df.index]
        mask = pd.Series([self.cfg.start <= d <= self.cfg.end for d in idx],
                         index=df.index)
        return df.loc[mask].copy()

    def _slice_series(self, s: pd.Series) -> pd.Series:
        if s is None or s.empty:
            return s
        idx = [self._d(ts) for ts in s.index]
        mask = pd.Series([self.cfg.start <= d <= self.cfg.end for d in idx],
                         index=s.index)
        return s.loc[mask].copy()

    def _vix_at(self, today: date) -> float | None:
        """Lookup VIX at `today` or last available before. None if unavailable."""
        # VIX is daily, but trading calendars match closely. Try exact match first.
        for ts in [pd.Timestamp(today)]:
            if ts in self.vix.index:
                return float(self.vix.loc[ts])
        # Fallback: use last value <= today
        prior = self.vix.loc[self.vix.index <= pd.Timestamp(today)]
        if prior.empty:
            return None
        return float(prior.iloc[-1])

    def _iv_for_tenor(self, today: date) -> float | None:
        """VIX-based IV proxy for the configured tenor."""
        v = self._vix_at(today)
        if v is None:
            return None
        return (v / 100.0) * self.cfg.vix_tenor_multiplier

    def _filter_on(self, today: date) -> bool:
        """SMA(fast) > SMA(slow) AND close > SMA(fast)."""
        i = self._spy_idx.get(today)
        if i is None or i < self.cfg.sma_slow:
            return False
        close = float(self.spy["close"].iloc[i])
        sma_fast = float(self.spy["close"].iloc[i - self.cfg.sma_fast + 1: i + 1].mean())
        sma_slow = float(self.spy["close"].iloc[i - self.cfg.sma_slow + 1: i + 1].mean())
        return close > sma_fast > sma_slow

    def _bs_value(self, spot: float, strike: float, dte: int, iv: float) -> float:
        return black_scholes_call(OptionParams(
            spot=spot, strike=strike, dte_days=dte, iv=iv,
            risk_free=self.cfg.risk_free, div_yield=self.cfg.div_yield,
        ))

    def _open_position(self, today: date, spot: float, iv: float) -> None:
        """Open a LEAPS at target delta and tenor. Charges half-spread on entry."""
        tenor_days = self.cfg.tenor_months * 30
        strike = find_strike_for_delta(
            spot=spot, dte_days=tenor_days, iv=iv,
            target_delta=self.cfg.target_delta,
            risk_free=self.cfg.risk_free, div_yield=self.cfg.div_yield,
        )
        mid = self._bs_value(spot, strike, tenor_days, iv)
        if mid <= 0.01:
            return
        ask = mid * (1 + self.cfg.spread_pct_of_mid / 2)
        # Sizing: target N contracts so n * fill * 100 = sizing_pct * equity
        target_dollars = self.cash * self.cfg.sizing_pct
        n = target_dollars / (ask * 100.0)
        if n <= 0:
            return
        cost = n * ask * 100.0
        if cost > self.cash:
            return
        self.cash -= cost
        self.position = _OpenLeapsPosition(
            open_date=today,
            strike=strike,
            expiry=today + timedelta(days=tenor_days),
            n_contracts=n,
            entry_premium=mid,
            entry_fill=ask,
            iv_at_entry=iv,
        )

    def _close_position(self, today: date, spot: float, iv: float, reason: str) -> None:
        """Sell current position at bid (mid - half-spread). Realize P&L."""
        if self.position is None:
            return
        dte = max(0, (self.position.expiry - today).days)
        mid = self._bs_value(spot, self.position.strike, dte, iv)
        bid = max(0.01, mid * (1 - self.cfg.spread_pct_of_mid / 2))
        proceeds = self.position.n_contracts * bid * 100.0
        pnl = (bid - self.position.entry_fill) * self.position.n_contracts * 100.0
        self.cash += proceeds
        self.trades.append(LeapsTrade(
            trade_id=str(uuid.uuid4()),
            open_date=self.position.open_date,
            close_date=today,
            strike=self.position.strike,
            expiry=self.position.expiry,
            n_contracts=self.position.n_contracts,
            entry_premium=self.position.entry_premium,
            entry_fill=self.position.entry_fill,
            exit_premium=mid,
            exit_fill=bid,
            pnl=pnl,
            hold_days=(today - self.position.open_date).days,
            reason=reason,
            iv_at_entry=self.position.iv_at_entry,
            iv_at_exit=iv,
        ))
        self.position = None

    def _equity_at_close(self, today: date, spot: float, iv: float) -> float:
        if self.position is None:
            return self.cash
        dte = max(0, (self.position.expiry - today).days)
        mid = self._bs_value(spot, self.position.strike, dte, iv)
        # Mark to mid (not bid) — symmetric with the leveraged-equity convention
        return self.cash + self.position.n_contracts * mid * 100.0

    def run(self) -> LeapsResult:
        idx = list(self.spy.index)
        for ts in idx:
            today = self._d(ts)
            spot = float(self.spy.loc[ts, "close"])
            iv = self._iv_for_tenor(today)
            if iv is None:
                # No VIX yet; equity remains cash-only
                self.equity_by_date[today] = self.cash
                continue

            on = self._filter_on(today)

            # Position management
            if self.position is not None:
                # Check filter flip
                if not on:
                    self._close_position(today, spot, iv, "filter_off")
                else:
                    # Check roll
                    dte = (self.position.expiry - today).days
                    if dte <= self.cfg.roll_when_dte_le:
                        self._close_position(today, spot, iv, "roll")
                        # Open new position at target delta + tenor immediately
                        self._open_position(today, spot, iv)
            elif on:
                # No position, filter ON: open
                self._open_position(today, spot, iv)

            self.equity_by_date[today] = self._equity_at_close(today, spot, iv)

        # Force-close at end of backtest
        if self.position is not None and idx:
            last_ts = idx[-1]
            today = self._d(last_ts)
            spot = float(self.spy.loc[last_ts, "close"])
            iv = self._iv_for_tenor(today) or self.position.iv_at_entry
            self._close_position(today, spot, iv, "end_of_backtest")
            self.equity_by_date[today] = self.cash

        eq = pd.Series(self.equity_by_date).sort_index()
        realized_pnl = sum(t.pnl for t in self.trades)
        position_value = self._equity_at_close(
            self._d(idx[-1]), float(self.spy.iloc[-1]["close"]),
            self._iv_for_tenor(self._d(idx[-1])) or 0.20,
        ) - self.cash
        return LeapsResult(
            config=self.cfg, trades=self.trades, equity_curve=eq,
            realized_pnl=realized_pnl, final_cash=self.cash,
            final_position_value=position_value,
        )
