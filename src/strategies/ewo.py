"""Strategy 1: EWO Mean Reversion (daily-close signals).

See STRATEGIES.md "Strategy 1" for the spec.

NOTE: this strategy is gated by EWO_ENABLED at the runner level. It also
emits a per-signal UNVALIDATED warning to the log because the 2018-2026
backtest (6 trades, 50% win, -$25 PnL) does not demonstrate edge at v1.0
thresholds. See DECISIONS.md for context.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from loguru import logger

from src.indicators import ewo_zscore, rsi, sma
from src.strategies.base import OptionSelection, Signal, SignalAction, Strategy

_INSTRUMENT_MAP = {
    "SPY": "UPRO",
    "QQQ": "TQQQ",
}
_SHORT_INSTRUMENT = "SQQQ"


@dataclass
class EWOConfig:
    long_z_spy: float = -2.0
    long_z_qqq: float = -2.2
    long_high_conviction_z: float = -2.5
    long_high_conviction_rsi: float = 5.0
    long_rsi_max: float = 10.0

    short_z_qqq: float = 2.2
    short_rsi_min: float = 90.0


class EWOStrategy(Strategy):
    name = "ewo"
    family = "mean_reversion"

    def __init__(self, config: EWOConfig | None = None, sqqq_short_enabled: bool = True):
        self.cfg = config or EWOConfig()
        self.sqqq_short_enabled = sqqq_short_enabled

    def on_daily_close(self, symbol: str, daily: pd.DataFrame) -> Signal | None:
        sym = symbol.upper()
        if sym not in {"SPY", "QQQ"}:
            return None
        if len(daily) < 252 + 35:
            return None  # need full lookback for z-score

        z = ewo_zscore(daily["high"], daily["low"], daily["close"]).iloc[-1]
        r = rsi(daily["close"], period=2).iloc[-1]
        sma200 = sma(daily["close"], 200).iloc[-1]
        close = daily["close"].iloc[-1]

        if any(pd.isna(x) for x in (z, r, sma200, close)):
            return None

        ts = daily.index[-1]

        # --- LONG ---
        z_thresh = self.cfg.long_z_spy if sym == "SPY" else self.cfg.long_z_qqq
        if z < z_thresh and r < self.cfg.long_rsi_max and close > sma200:
            high_conv = z < self.cfg.long_high_conviction_z and r < self.cfg.long_high_conviction_rsi
            logger.warning(
                f"EWO signal fired UNVALIDATED_LOW_N {sym}: "
                f"8-year backtest n=6 / 50% win / -$25 PnL. See DECISIONS.md."
            )
            return Signal(
                action=SignalAction.LONG,
                underlying=sym,
                option=OptionSelection(
                    underlying_etf=_INSTRUMENT_MAP[sym],
                    right="C",
                    target_dte_days=(10, 14),
                    strike_offset=-1 if high_conv else 0,
                ),
                contracts=1,
                reason=(f"EWO long {sym}: z={z:.2f}<{z_thresh}, RSI(2)={r:.1f}, "
                        f"close>{sma200:.2f} SMA200"
                        f"{' [HIGH CONV]' if high_conv else ''}"),
                strategy_name=self.name,
                strategy_family=self.family,
                fired_at=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
            )

        # --- SHORT (QQQ only) ---
        if (sym == "QQQ"
                and self.sqqq_short_enabled
                and z > self.cfg.short_z_qqq
                and r > self.cfg.short_rsi_min
                and close < sma200):
            logger.warning(
                f"EWO short signal fired UNVALIDATED_LOW_N {sym}: "
                f"8-year backtest n=6 / 50% win / -$25 PnL. See DECISIONS.md."
            )
            return Signal(
                action=SignalAction.SHORT_FADE,
                underlying=sym,
                option=OptionSelection(
                    underlying_etf=_SHORT_INSTRUMENT,
                    right="C",
                    target_dte_days=(10, 14),
                    strike_offset=0,
                ),
                contracts=1,
                reason=(f"EWO short {sym} via SQQQ: z={z:.2f}>{self.cfg.short_z_qqq}, "
                        f"RSI(2)={r:.1f}, close<{sma200:.2f} SMA200"),
                strategy_name=self.name,
                strategy_family=self.family,
                fired_at=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
            )

        return None
