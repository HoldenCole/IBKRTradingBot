"""Exit evaluation.

Single entry point: `evaluate_exit(pos, market) -> ExitAction`. Walks the
priority order from STRATEGIES.md:

  1. -50% premium stop          (CLOSE_ALL, stop-loss path = bypasses ladder)
  2. Blackout flatten           (CLOSE_ALL, 15m pre-release; not for afternoon)
  3. Time stop                  (CLOSE_ALL, 3d EWO / 2d IBS / 2d Afternoon)
  4. DTE stop                   (CLOSE_ALL, at <=2 DTE)
  5. Strategy-specific exit     (CLOSE_ALL or partial scale)
  6. Profit scale targets       (SCALE at +50% and +100% premium)
  7. Trailing stop on runner    (CLOSE_ALL of remaining)

First applicable wins.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional

import pandas as pd

from src.indicators import ibs as ibs_ind
from src.indicators import rsi, sma
from src.positions.position import Position
from src.risk.blackout import BlackoutChecker
from src.strategies.base import SignalAction


class ExitKind(str, Enum):
    NONE = "none"
    CLOSE_ALL = "close_all"
    SCALE_OUT = "scale_out"


class ExitReason(str, Enum):
    PREMIUM_STOP = "premium_stop"
    BLACKOUT_FLATTEN = "blackout_flatten"
    TIME_STOP = "time_stop"
    DTE_STOP = "dte_stop"
    SIGNAL_EXIT = "signal_exit"
    SCALE_OUT_50 = "scale_out_+50pct"
    SCALE_OUT_100 = "scale_out_+100pct"
    TRAIL_STOP = "trail_stop"
    AFTERNOON_HARD_STOP = "afternoon_hard_stop"
    AFTERNOON_VWAP_RECLAIM = "afternoon_vwap_reclaim"
    OVERNIGHT_BREAKEVEN = "overnight_breakeven"


@dataclass(frozen=True)
class ExitAction:
    kind: ExitKind
    contracts_to_close: int
    reason: ExitReason | None = None
    detail: str = ""
    use_stop_loss_path: bool = False  # skip the fill ladder, dump at bid - 0.05

    @classmethod
    def none(cls) -> "ExitAction":
        return cls(kind=ExitKind.NONE, contracts_to_close=0)


@dataclass
class MarketState:
    now: datetime
    today: date
    option_premium: float                 # current option mid-price
    underlying_price: float
    daily_bars: pd.DataFrame              # underlying daily OHLCV, indexed by date
    blackout: BlackoutChecker
    intraday_session: Optional[pd.DataFrame] = None  # afternoon-only; ET-tz index
    morning_close: Optional[float] = None             # afternoon: today's session-end close

    def underlying_change_since_entry(self, pos: Position) -> float:
        return self.underlying_price - pos.entry_underlying


# --- Helpers --------------------------------------------------------------

def _premium_pnl_pct(pos: Position, current_premium: float) -> float:
    """% change in option premium vs entry, signed by direction.
    For both LONG and SHORT_FADE the option is a CALL we are long -> premium
    going up is good in both cases (the SHORT_FADE leg is long SQQQ calls).
    """
    if pos.entry_premium <= 0:
        return 0.0
    return (current_premium - pos.entry_premium) / pos.entry_premium


def _vwap_session(session: pd.DataFrame) -> float | None:
    """Compute session VWAP up to the latest bar."""
    if session.empty:
        return None
    tp = (session["high"] + session["low"] + session["close"]) / 3.0
    cum_vol = session["volume"].cumsum().iloc[-1]
    if cum_vol == 0:
        return None
    return float((tp * session["volume"]).cumsum().iloc[-1] / cum_vol)


# --- Universal exits (in priority order) ---------------------------------

def _check_premium_stop(pos: Position, market: MarketState) -> ExitAction | None:
    pnl_pct = _premium_pnl_pct(pos, market.option_premium)
    if pnl_pct <= -0.50:
        return ExitAction(
            kind=ExitKind.CLOSE_ALL,
            contracts_to_close=pos.contracts_remaining,
            reason=ExitReason.PREMIUM_STOP,
            detail=f"premium {pnl_pct:.1%} <= -50%",
            use_stop_loss_path=True,
        )
    return None


def _check_blackout_flatten(pos: Position, market: MarketState) -> ExitAction | None:
    # Afternoon family is already blocked from entering on blackout days; if
    # somehow open, still flatten ahead of news.
    imminent = market.blackout.imminent_release(market.now)
    if imminent is not None:
        return ExitAction(
            kind=ExitKind.CLOSE_ALL,
            contracts_to_close=pos.contracts_remaining,
            reason=ExitReason.BLACKOUT_FLATTEN,
            detail=f"flatten 15m pre-{imminent.kind.value}",
        )
    return None


def _check_dte_stop(pos: Position, market: MarketState) -> ExitAction | None:
    if pos.days_to_expiry(market.today) <= 2:
        return ExitAction(
            kind=ExitKind.CLOSE_ALL,
            contracts_to_close=pos.contracts_remaining,
            reason=ExitReason.DTE_STOP,
            detail=f"DTE={pos.days_to_expiry(market.today)} <= 2",
        )
    return None


# --- Per-strategy time stops ---------------------------------------------

_TIME_STOP_DAYS = {
    "ewo": 3,
    "ibs": 2,
    "afternoon_reversion": 2,
}


def _check_time_stop(pos: Position, market: MarketState) -> ExitAction | None:
    cap = _TIME_STOP_DAYS.get(pos.strategy_name)
    if cap is None:
        return None
    if pos.trading_days_held >= cap:
        return ExitAction(
            kind=ExitKind.CLOSE_ALL,
            contracts_to_close=pos.contracts_remaining,
            reason=ExitReason.TIME_STOP,
            detail=f"{pos.strategy_name} held {pos.trading_days_held}d >= {cap}d cap",
        )
    return None


# --- Per-strategy signal exits -------------------------------------------

def _ewo_signal_exit(pos: Position, market: MarketState) -> ExitAction | None:
    daily = market.daily_bars
    if len(daily) < 6:
        return None
    sma5 = sma(daily["close"], 5).iloc[-1]
    rsi2 = rsi(daily["close"], period=2).iloc[-1]
    last_close = daily["close"].iloc[-1]
    if pd.isna(sma5) or pd.isna(rsi2):
        return None

    if pos.is_long:
        if last_close > sma5:
            return ExitAction(
                kind=ExitKind.CLOSE_ALL,
                contracts_to_close=pos.contracts_remaining,
                reason=ExitReason.SIGNAL_EXIT,
                detail=f"close {last_close:.2f} > SMA5 {sma5:.2f}",
            )
        if rsi2 > 70:
            return ExitAction(
                kind=ExitKind.CLOSE_ALL,
                contracts_to_close=pos.contracts_remaining,
                reason=ExitReason.SIGNAL_EXIT,
                detail=f"RSI(2)={rsi2:.1f} > 70",
            )
    else:  # SHORT_FADE: mirror
        if last_close < sma5:
            return ExitAction(
                kind=ExitKind.CLOSE_ALL,
                contracts_to_close=pos.contracts_remaining,
                reason=ExitReason.SIGNAL_EXIT,
                detail=f"close {last_close:.2f} < SMA5 {sma5:.2f}",
            )
        if rsi2 < 30:
            return ExitAction(
                kind=ExitKind.CLOSE_ALL,
                contracts_to_close=pos.contracts_remaining,
                reason=ExitReason.SIGNAL_EXIT,
                detail=f"RSI(2)={rsi2:.1f} < 30",
            )
    return None


def _ibs_signal_exit(pos: Position, market: MarketState) -> ExitAction | None:
    daily = market.daily_bars
    if len(daily) < 2:
        return None
    today_high = daily["high"].iloc[-1]
    today_low = daily["low"].iloc[-1]
    today_close = daily["close"].iloc[-1]
    prior_high = daily["high"].iloc[-2]
    prior_low = daily["low"].iloc[-2]
    today_ibs_val = ibs_ind(daily["high"], daily["low"], daily["close"]).iloc[-1]

    if pos.is_long:
        if today_close > prior_high:
            return ExitAction(
                kind=ExitKind.CLOSE_ALL,
                contracts_to_close=pos.contracts_remaining,
                reason=ExitReason.SIGNAL_EXIT,
                detail=f"close {today_close:.2f} > prior high {prior_high:.2f}",
            )
        if pd.notna(today_ibs_val) and today_ibs_val > 0.70:
            return ExitAction(
                kind=ExitKind.CLOSE_ALL,
                contracts_to_close=pos.contracts_remaining,
                reason=ExitReason.SIGNAL_EXIT,
                detail=f"IBS={today_ibs_val:.2f} > 0.70",
            )
    else:
        if today_close < prior_low:
            return ExitAction(
                kind=ExitKind.CLOSE_ALL,
                contracts_to_close=pos.contracts_remaining,
                reason=ExitReason.SIGNAL_EXIT,
                detail=f"close {today_close:.2f} < prior low {prior_low:.2f}",
            )
        if pd.notna(today_ibs_val) and today_ibs_val < 0.30:
            return ExitAction(
                kind=ExitKind.CLOSE_ALL,
                contracts_to_close=pos.contracts_remaining,
                reason=ExitReason.SIGNAL_EXIT,
                detail=f"IBS={today_ibs_val:.2f} < 0.30",
            )
    return None


def _afternoon_signal_exit(pos: Position, market: MarketState) -> ExitAction | None:
    """Afternoon Reversion has its own intraday exit set:
      1. VWAP reclaim -> scale 50% (only first time it triggers)
      2. Hard stop: 0.5 × morning range against entry -> CLOSE_ALL
      3. Overnight: first reclaim of entry underlying price -> CLOSE_ALL
    """
    if market.intraday_session is None:
        return None
    underlying = market.underlying_price

    # Hard stop (highest urgency among afternoon-specific)
    morning_range = pos.morning_range()
    if morning_range is not None:
        threshold = 0.5 * morning_range
        if pos.is_long and underlying <= pos.entry_underlying - threshold:
            return ExitAction(
                kind=ExitKind.CLOSE_ALL,
                contracts_to_close=pos.contracts_remaining,
                reason=ExitReason.AFTERNOON_HARD_STOP,
                detail=f"underlying {underlying:.2f} <= entry {pos.entry_underlying:.2f} - 0.5*range",
                use_stop_loss_path=True,
            )
        if (not pos.is_long) and underlying >= pos.entry_underlying + threshold:
            return ExitAction(
                kind=ExitKind.CLOSE_ALL,
                contracts_to_close=pos.contracts_remaining,
                reason=ExitReason.AFTERNOON_HARD_STOP,
                detail=f"underlying {underlying:.2f} >= entry + 0.5*range",
                use_stop_loss_path=True,
            )

    # Overnight reclaim of entry premium (option), per spec
    if pos.held_overnight:
        if pos.is_long and market.option_premium >= pos.entry_premium:
            return ExitAction(
                kind=ExitKind.CLOSE_ALL,
                contracts_to_close=pos.contracts_remaining,
                reason=ExitReason.OVERNIGHT_BREAKEVEN,
                detail="overnight: reclaimed entry premium",
            )

    # VWAP reclaim — scale 50% (only first time, only if not yet scaled)
    if not pos.scaled_50pct:
        v = _vwap_session(market.intraday_session)
        if v is not None:
            if pos.is_long and underlying >= v:
                qty = max(1, pos.contracts_remaining // 2)
                return ExitAction(
                    kind=ExitKind.SCALE_OUT,
                    contracts_to_close=qty,
                    reason=ExitReason.AFTERNOON_VWAP_RECLAIM,
                    detail=f"underlying {underlying:.2f} >= VWAP {v:.2f}",
                )
            if (not pos.is_long) and underlying <= v:
                qty = max(1, pos.contracts_remaining // 2)
                return ExitAction(
                    kind=ExitKind.SCALE_OUT,
                    contracts_to_close=qty,
                    reason=ExitReason.AFTERNOON_VWAP_RECLAIM,
                    detail=f"underlying {underlying:.2f} <= VWAP {v:.2f}",
                )
    return None


_SIGNAL_EXIT_FN = {
    "ewo": _ewo_signal_exit,
    "ibs": _ibs_signal_exit,
    "afternoon_reversion": _afternoon_signal_exit,
}


# --- Profit scale-outs and trail -----------------------------------------

def _check_scale_out(pos: Position, market: MarketState) -> ExitAction | None:
    pnl = _premium_pnl_pct(pos, market.option_premium)
    if not pos.scaled_50pct and pnl >= 0.50:
        qty = max(1, pos.initial_contracts // 2)
        # Don't try to close more than remaining.
        qty = min(qty, pos.contracts_remaining)
        return ExitAction(
            kind=ExitKind.SCALE_OUT,
            contracts_to_close=qty,
            reason=ExitReason.SCALE_OUT_50,
            detail=f"premium +{pnl:.0%}",
        )
    if pos.scaled_50pct and not pos.scaled_100pct and pnl >= 1.00:
        qty = max(1, pos.initial_contracts // 4)
        qty = min(qty, pos.contracts_remaining)
        return ExitAction(
            kind=ExitKind.SCALE_OUT,
            contracts_to_close=qty,
            reason=ExitReason.SCALE_OUT_100,
            detail=f"premium +{pnl:.0%}",
        )
    return None


def update_trail_level(pos: Position, market: MarketState) -> None:
    """Ratchet the ATR-based trail on the underlying. Called every tick before
    `_check_trail_stop`. No-op until both scale-outs are done.
    """
    if not pos.scaled_100pct:
        return
    pos.trail_active = True
    band = 1.5 * pos.entry_atr20
    pos.update_high_water(market.underlying_price)
    if pos.is_long and pos.high_water_underlying is not None:
        candidate = pos.high_water_underlying - band
        if pos.trail_level is None or candidate > pos.trail_level:
            pos.trail_level = candidate
    elif (not pos.is_long) and pos.low_water_underlying is not None:
        candidate = pos.low_water_underlying + band
        if pos.trail_level is None or candidate < pos.trail_level:
            pos.trail_level = candidate


def _check_trail_stop(pos: Position, market: MarketState) -> ExitAction | None:
    if not pos.trail_active or pos.trail_level is None:
        return None
    if pos.is_long and market.underlying_price < pos.trail_level:
        return ExitAction(
            kind=ExitKind.CLOSE_ALL,
            contracts_to_close=pos.contracts_remaining,
            reason=ExitReason.TRAIL_STOP,
            detail=f"underlying {market.underlying_price:.2f} < trail {pos.trail_level:.2f}",
        )
    if (not pos.is_long) and market.underlying_price > pos.trail_level:
        return ExitAction(
            kind=ExitKind.CLOSE_ALL,
            contracts_to_close=pos.contracts_remaining,
            reason=ExitReason.TRAIL_STOP,
            detail=f"underlying {market.underlying_price:.2f} > trail {pos.trail_level:.2f}",
        )
    return None


# --- Public entry point ---------------------------------------------------

def evaluate_exit(pos: Position, market: MarketState) -> ExitAction:
    """Walk the priority ladder. First fire wins."""
    update_trail_level(pos, market)

    for check in (_check_premium_stop, _check_blackout_flatten, _check_time_stop,
                  _check_dte_stop):
        action = check(pos, market)
        if action is not None:
            return action

    sig_fn = _SIGNAL_EXIT_FN.get(pos.strategy_name)
    if sig_fn is not None:
        action = sig_fn(pos, market)
        if action is not None:
            return action

    action = _check_scale_out(pos, market)
    if action is not None:
        return action

    action = _check_trail_stop(pos, market)
    if action is not None:
        return action

    return ExitAction.none()
