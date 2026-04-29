"""Strategy 2: Afternoon Reversion — intraday signals.

Uses 5-min bars. Observation window 09:30-11:00 ET; trigger window 11:00-11:30 ET.
See STRATEGIES.md "Strategy 2" for the spec.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo

import pandas as pd

from src.indicators import atr
from src.strategies.base import OptionSelection, Signal, SignalAction, Strategy

ET = ZoneInfo("America/New_York")
_INSTRUMENT_MAP = {"SPY": "UPRO", "QQQ": "TQQQ"}


@dataclass
class AfternoonConfig:
    obs_start: time = time(9, 30)
    obs_end: time = time(11, 0)
    trigger_end: time = time(11, 30)
    move_atr_multiple: float = 0.6
    high_conv_atr_multiple: float = 1.2
    near_extreme_pct: float = 0.15  # within 15% of morning low/high
    confirm_pct: float = 0.0008     # 0.08%


class AfternoonReversionStrategy(Strategy):
    name = "afternoon_reversion"
    family = "afternoon"

    def __init__(self, config: AfternoonConfig | None = None):
        self.cfg = config or AfternoonConfig()
        self._signaled_today: set[tuple[str, pd.Timestamp]] = set()

    def on_intraday_bar(
        self, symbol: str, bar: dict, session: pd.DataFrame,
    ) -> Signal | None:
        """`bar` is the just-closed 5-min bar dict {ts, open, high, low, close, volume}.
        `session` is intraday bars for today indexed by tz-aware ET timestamps.
        """
        sym = symbol.upper()
        if sym not in {"SPY", "QQQ"}:
            return None

        ts: pd.Timestamp = bar["ts"]
        if ts.tzinfo is None:
            ts = ts.tz_localize(ET)
        else:
            ts = ts.tz_convert(ET)

        # Only fire inside the trigger window 11:00 < ts <= 11:30
        if not (self.cfg.obs_end < ts.time() <= self.cfg.trigger_end):
            return None

        day_key = (sym, ts.normalize())
        if day_key in self._signaled_today:
            return None

        # Slice the morning observation window from the session.
        obs = session.between_time(self.cfg.obs_start, self.cfg.obs_end, inclusive="left")
        if obs.empty:
            return None

        morning_open = obs["open"].iloc[0]
        morning_high = obs["high"].max()
        morning_low = obs["low"].min()
        morning_range = morning_high - morning_low
        if morning_range <= 0:
            return None

        price_at_1100 = obs["close"].iloc[-1]
        # Morning return: open -> 11:00
        morning_return = (price_at_1100 - morning_open) / morning_open

        # ATR(20) on daily bars must come from `session.attrs["daily_atr20"]` —
        # the runner attaches this so we don't refetch daily history per bar.
        daily_atr20 = session.attrs.get("daily_atr20")
        if daily_atr20 is None or daily_atr20 <= 0:
            return None
        # Express ATR as a fraction of the morning_open so the threshold is
        # comparable to morning_return.
        atr_frac = daily_atr20 / morning_open

        confirm_close = bar["close"]

        # --- LONG: faded morning sell-off ---
        if morning_return < 0 and abs(morning_return) > self.cfg.move_atr_multiple * atr_frac:
            near_low = abs(price_at_1100 - morning_low) / morning_range <= self.cfg.near_extreme_pct
            confirm_above = (confirm_close - morning_low) / morning_low >= self.cfg.confirm_pct
            if near_low and confirm_above:
                high_conv = abs(morning_return) > self.cfg.high_conv_atr_multiple * atr_frac
                self._signaled_today.add(day_key)
                return Signal(
                    action=SignalAction.LONG,
                    underlying=sym,
                    option=OptionSelection(
                        underlying_etf=_INSTRUMENT_MAP[sym],
                        right="C",
                        target_dte_days=(5, 9),
                        # Default 1-strike ITM; high-conv flips to ATM (per spec)
                        strike_offset=0 if high_conv else -1,
                    ),
                    contracts=1,
                    reason=(f"Afternoon long {sym}: morning_ret={morning_return:.2%}, "
                            f"|move|>{self.cfg.move_atr_multiple}*ATR, near low, confirmed"
                            f"{' [HIGH CONV ATM]' if high_conv else ''}"),
                    strategy_name=self.name,
                    strategy_family=self.family,
                    fired_at=ts.to_pydatetime(),
                    invalidation_price=morning_low,
                )

        # --- SHORT (QQQ only): faded morning rip ---
        if (sym == "QQQ"
                and morning_return > 0
                and morning_return > self.cfg.move_atr_multiple * atr_frac):
            near_high = abs(morning_high - price_at_1100) / morning_range <= self.cfg.near_extreme_pct
            confirm_below = (morning_high - confirm_close) / morning_high >= self.cfg.confirm_pct
            if near_high and confirm_below:
                self._signaled_today.add(day_key)
                return Signal(
                    action=SignalAction.SHORT_FADE,
                    underlying=sym,
                    option=OptionSelection(
                        underlying_etf="SQQQ",
                        right="C",
                        target_dte_days=(5, 9),
                        strike_offset=-1,
                    ),
                    contracts=1,
                    reason=(f"Afternoon short {sym} via SQQQ: morning_ret={morning_return:.2%}, "
                            f"near high, confirmed below"),
                    strategy_name=self.name,
                    strategy_family=self.family,
                    fired_at=ts.to_pydatetime(),
                    invalidation_price=morning_high,
                )

        return None


def attach_daily_atr(session: pd.DataFrame, daily: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Helper: stash ATR(20) for the underlying onto the intraday session frame."""
    a = atr(daily["high"], daily["low"], daily["close"], period=period).iloc[-1]
    session = session.copy()
    session.attrs["daily_atr20"] = float(a) if pd.notna(a) else None
    return session
