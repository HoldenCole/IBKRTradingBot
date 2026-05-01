"""Strategy 3: IBS (Internal Bar Strength) — daily close signals.

See STRATEGIES.md "Strategy 3" for the spec.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.indicators import ibs as ibs_ind
from src.indicators import sma
from src.strategies.base import OptionSelection, Signal, SignalAction, Strategy

_INSTRUMENT_MAP = {"SPY": "UPRO", "QQQ": "TQQQ"}


@dataclass
class IBSConfig:
    long_threshold_spy: float = 0.20
    long_threshold_qqq: float = 0.25
    short_threshold_qqq: float = 0.80


class IBSStrategy(Strategy):
    name = "ibs"
    family = "mean_reversion"

    def __init__(self, config: IBSConfig | None = None, sqqq_short_enabled: bool = True):
        self.cfg = config or IBSConfig()
        self.sqqq_short_enabled = sqqq_short_enabled

    def on_daily_close(self, symbol: str, daily: pd.DataFrame) -> Signal | None:
        sym = symbol.upper()
        if sym not in {"SPY", "QQQ"}:
            return None
        if len(daily) < 201:
            return None

        ibs_series = ibs_ind(daily["high"], daily["low"], daily["close"])
        sma200 = sma(daily["close"], 200).iloc[-1]
        today_ibs = ibs_series.iloc[-1]
        prior_ibs = ibs_series.iloc[-2]
        close = daily["close"].iloc[-1]

        if any(pd.isna(x) for x in (today_ibs, prior_ibs, sma200, close)):
            return None

        ts = daily.index[-1]

        # --- LONG ---
        long_thresh = self.cfg.long_threshold_spy if sym == "SPY" else self.cfg.long_threshold_qqq
        if today_ibs < long_thresh and close > sma200 and prior_ibs >= long_thresh:
            return Signal(
                action=SignalAction.LONG,
                underlying=sym,
                option=OptionSelection(
                    underlying_etf=_INSTRUMENT_MAP[sym],
                    right="C",
                    target_dte_days=(7, 9),
                    strike_offset=0,  # ATM
                ),
                contracts=1,
                reason=(f"IBS long {sym}: IBS={today_ibs:.2f}<{long_thresh}, "
                        f"close>{sma200:.2f} SMA200, prior IBS={prior_ibs:.2f}"),
                strategy_name=self.name,
                strategy_family=self.family,
                fired_at=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
            )

        # --- SHORT (QQQ only) ---
        if (sym == "QQQ"
                and self.sqqq_short_enabled
                and today_ibs > self.cfg.short_threshold_qqq
                and close < sma200
                and prior_ibs <= self.cfg.short_threshold_qqq):
            return Signal(
                action=SignalAction.SHORT_FADE,
                underlying=sym,
                option=OptionSelection(
                    underlying_etf="SQQQ",
                    right="C",
                    target_dte_days=(7, 9),
                    strike_offset=0,
                ),
                contracts=1,
                reason=(f"IBS short {sym} via SQQQ: IBS={today_ibs:.2f}>"
                        f"{self.cfg.short_threshold_qqq}, close<{sma200:.2f} SMA200"),
                strategy_name=self.name,
                strategy_family=self.family,
                fired_at=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
            )

        return None
